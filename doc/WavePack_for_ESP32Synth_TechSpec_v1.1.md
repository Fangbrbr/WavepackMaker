# WavePack for ESP32Synth 技术规范 v1.1

> **版本**：v1.1（二进制 `version` 字段 `0x0101`）  
> **目标平台**：ESP32-P4（M5Stack Tab5）  
> **底层引擎**：ESP32Synth v2.4.1  
> **文档日期**：2026-07-11  
> **适用范围**：上位机工具链开发（打包器、编辑器、校验工具）与下位机加载器实现  
> **约束前提**：引擎音频路径禁止浮点与除法；一个 `.wavepack` 文件代表一个完整音色（Preset）。

---

## 1. 设计目标与核心原则

### 1.1 WavePack 是什么

**一个 `.wavepack` 文件代表一个完整音色（Preset）**。它把同一乐器在不同音域、不同力度层下所需的多个采样封装成一个二进制文件，运行时通过 MIDI Note 与 Velocity 命中对应的采样条目。

典型应用场景：

- **钢琴音色**：用 C2、C4、C6 三个根音采样覆盖低/中/高音区，解决单一 C4 采样跨八度拉伸后音质劣化的问题。
- **鼓组音色**：把 Kick、Snare、Hi-Hat 等打击乐采样封装在一起，每个 Zone 的 `min_note == max_note`，对应 GM Drum Map（Note 36 = Kick、38 = Snare、42 = Closed Hi-Hat 等）。

### 1.2 WavePack 不是什么

- **不是音色库管理器**：不包含 Kit、Bank、Program 等层级概念；一个文件就是一个音色。
- **不处理 MIDI Channel**：Channel 由 App 框架与 `engine_midi` 总线决定；WavePack 格式内部只识别 Note 与 Velocity。
- **不包含乐理元数据**：调性、指法、音名显示、教学提示等属于上层 App / UI 框架，不在本格式中定义。
- **不是唯一的音频源**：现场采样、内置波表等可直接注册到 ESP32Synth，不必封装成 WavePack。

### 1.3 核心原则

| 原则 | 说明 |
|---|---|
| 零运行时解析 | 下位机启动时一次性加载元数据到 SRAM，运行时只做数组索引。 |
| 零浮点 | 音高、包络、混音全部使用定点数或整数查表；浮点运算只允许出现在加载阶段或上位机打包阶段。 |
| 单音色单文件 | 任一时刻，ESP32Synth 只加载一个 `.wavepack` 音色。 |
| 前后端隔离 | 上位机只负责生成 `.wavepack`；下位机只负责加载、查找、发声。 |
| 与引擎原生模型对齐 | `.wavepack` 是 WavePack Maker 自定义的运行时加载格式，下位机加载器负责把它映射到 ESP32Synth 原生的 `SampleData` / `SampleZone` / `Instrument_Sample` 结构。 |

---

## 2. 与 ESP32Synth 引擎的关系

### 2.1 引擎原生数据模型

ESP32Synth 引擎本身**没有原生 `.wavepack` 解析器**，它通过内存中的 C 结构体消费采样：

```c
// ESP32Synth.h
struct SampleData {
    const void* data;            // PCM 数据指针
    uint32_t    length;          // 采样帧数（不是字节数）
    uint32_t    sampleRate;      // 采样率
    uint32_t    rootFreqCentiHz; // 根音频率 ×100（centiHz）
    BitDepth    depth;           // BITS_4 / BITS_8 / BITS_16
};

struct SampleZone {
    uint32_t lowFreq;       // 频率下限（centiHz）
    uint32_t highFreq;      // 频率上限（centiHz）
    uint16_t sampleId;      // 注册采样时用的 sampleId
    uint32_t rootOverride;  // 根音覆盖，0 表示使用 SampleData.rootFreqCentiHz
};

struct Instrument_Sample {
    const SampleZone* zones;
    uint8_t           numZones;
    LoopMode          loopMode;
    uint32_t          loopStart;
    uint32_t          loopEnd;
};
```

引擎按 **频率范围（centiHz）** 命中 `SampleZone`，根音以 **centiHz** 形式参与播放速度计算：

```c
// ESP32Synth_Core.hpp 核心逻辑
uint64_t ratio1616 = ((uint64_t)freqCentiHz << 16) / root;
vo->sampleInc1616  = (uint32_t)((ratio1616 * sData->sampleRate) / _sampleRate);
```

### 2.2 WavePack 与引擎的阻抗

| 维度 | WavePack 格式 | ESP32Synth 引擎原生结构 |
|---|---|---|
| Zone 命中键 | `(min_note, max_note, min_vel, max_vel)` | `(lowFreq, highFreq)`（频率范围） |
| 根音表示 | `Sample.root_note`（MIDI note，0~127） | `SampleData.rootFreqCentiHz`（Hz×100） |
| 力度分层 | 支持 `min_vel/max_vel` | `SampleZone` 无 velocity 字段 |
| ADSR / Filter / Reverb / Pitch cents | Zone Entry 携带 | `SampleZone` / `Instrument_Sample` 无这些字段 |
| Loop 归属 | `Sample Entry`（每个采样独立） | `Instrument_Sample`（乐器级） |
| 位深 | 当前仅 16-bit mono | 原生支持 4/8/16-bit |

因此，**`.wavepack` 不能直接灌入引擎**，必须由下位机加载器做一次格式映射。

### 2.3 下位机加载器职责

下位机加载器至少需要完成以下转换：

1. 解析 `.wavepack` Header、Zone Directory、Sample Directory。
2. 将 `WavePackSample.root_note` 通过 `MIDI_TO_CENTIHZ_LUT` 转换为 `rootFreqCentiHz`。
3. 将 `WavePackSample.data_offset`（相对 PCM 区起始）转换为绝对文件偏移，加载 PCM 到 PSRAM/SRAM。
4. 将 `data_size`（字节）除以 `bits_per_sample / 8` 得到采样帧数 `length`。
5. 对每个 Zone，把 `min_note/max_note` 转换为 centiHz 范围，填充引擎 `SampleZone.lowFreq/highFreq`。
6. `SampleZone.rootOverride` 应置 `0`，让引擎使用 `SampleData.rootFreqCentiHz`。
7. 将 Zone 的 ADSR、`pitch_cents`、filter、reverb 通过引擎其他 API（如 `setEnv()`）在触发 voice 后设置。
8. 将每个 Zone/Sample 的 loop 信息合并到 `Instrument_Sample` 或等效 API 调用中。

---

## 3. WavePack 格式规范（v1.1）

### 3.1 文件结构（小端序）

```
[Header]           64 bytes
[Zone Directory]   N × 48 bytes
[Sample Directory] M × 32 bytes
[Padding]          对齐到 4096 bytes (Flash page)
[Sample Data]      连续的 PCM s16le 块
```

- **字节序**：全部小端（little-endian）。
- **对齐**：PCM 数据区起始按 4096 bytes 对齐；每个采样 PCM 块再按 4 bytes 补零。

### 3.2 Header（64 bytes）

```c
typedef struct __attribute__((packed)) {
    char     magic[8];          // "WAVEPACK"
    uint16_t version;           // 0x0101（v1.1）
    uint16_t num_zones;         // Zone 条目数
    uint16_t num_samples;       // Sample 条目数
    uint16_t flags;             // bit0: 16bit PCM（固定为 1）；bit1~15: 预留
    uint32_t zone_dir_offset;   // 固定 64
    uint32_t sample_dir_offset; // 64 + num_zones * 48
    uint32_t data_offset;       // 采样数据起始（已 4KB 对齐）
    uint32_t data_size;         // 采样数据总字节数
    uint32_t sample_rate;       // 全局采样率（如 44100）
    uint32_t reserved[6];       // 预留
    uint32_t crc32;             // 整个文件 CRC32（可选，0 表示未计算）
} WavePackHeader;
```

**字段约束**：

- `version` 必须为 `0x0101`；下位机加载时若版本不匹配，应拒绝加载。
- `flags` 当前固定为 `0x0001`，表示 16-bit PCM mono。
- `crc32` 为上位机可选生成；下位机加载时若值为 0 则跳过校验。
- `zone_dir_offset` 固定为 64；`sample_dir_offset = 64 + num_zones * 48`。
- `data_offset` 必须按 4096 字节对齐，满足 ESP32 内存映射与 DMA 对齐要求。

### 3.3 Zone Entry（48 bytes）

```c
typedef struct __attribute__((packed)) {
    uint8_t  zone_id;           // 0~255，调试用，不参与查找
    uint8_t  sample_idx;        // 指向 Sample Directory 的索引，必须 < num_samples
    uint8_t  min_note;          // 音域下限（0~127）
    uint8_t  max_note;          // 音域上限（0~127），必须 >= min_note
    uint8_t  min_vel;           // 力度下限（0~127）
    uint8_t  max_vel;           // 力度上限（0~127），必须 >= min_vel
    uint8_t  flags;             // 见 ZONE_FLAG_* 定义
    uint8_t  reserved0;         // 对齐填充

    uint16_t attack_ms;         // ADSR Attack（ms）
    uint16_t decay_ms;          // ADSR Decay（ms）
    uint16_t sustain_level;     // Sustain 等级（0~255）
    uint16_t release_ms;        // ADSR Release（ms）

    int16_t  pitch_cents;       // 音高微调（-100 ~ +100 cents，1 semitone = 100 cents）
    uint16_t filter_cutoff;     // 预留：低通截止频率（0 = 禁用）
    uint16_t filter_resonance;  // 预留
    uint16_t reverb_send;       // 预留：混响发送量

    uint32_t reserved[6];       // 对齐到 48 bytes
} WavePackZone;
```

**ADSR 字段说明**：

| 字段 | 类型 | 范围 | 说明 |
|---|---|---|---|
| `attack_ms` | uint16 | 0~65535 | Attack 阶段时长，单位毫秒。 |
| `decay_ms` | uint16 | 0~65535 | Decay 阶段时长，单位毫秒。 |
| `sustain_level` | uint16 | 0~255 | Sustain 阶段音量电平，255 表示峰值。 |
| `release_ms` | uint16 | 0~65535 | Release 阶段时长，单位毫秒。 |

这些字段按原样写入二进制文件，下位机加载后传递给 ESP32Synth 的包络接口。

**Zone `flags` 定义**：

```c
#define ZONE_FLAG_PERCUSSION            0x00  // bit0=0: 固定音高，按 Sample.root_note 原样播放
#define ZONE_FLAG_MELODIC               0x01  // bit0=1: 可拉伸，按目标 note 计算 pitch shift
#define ZONE_FLAG_LOOP                  0x02  // bit1: 强制循环（可覆盖 Sample 自身 loop 设置）

// bit2~3: 复音模式
#define ZONE_FLAG_POLY_RETRIGGER        0x00  // 同音重触发
#define ZONE_FLAG_POLY_MULTI            0x04  // 同音允许多 Voice 叠加
#define ZONE_FLAG_POLY_LEGATO           0x08  // 同音复用，仅变 pitch（滑音）
#define ZONE_FLAG_POLY_MASK             0x0C

// bit4~7: 同音最大 Voice 数 - 1，范围 0~15（即最多 1~16 个）
#define ZONE_FLAG_MAX_SAME_NOTE_SHIFT   4
#define ZONE_FLAG_MAX_SAME_NOTE_MASK    0xF0
```

**Zone 设计规则**：

- 一个 Zone 描述一种"发声映射"：在什么 note 范围、什么 velocity 范围内，触发哪个采样。
- 多个 Zone 可以指向同一个 Sample，用于力度分层。
- 一个 Zone 唯一绑定一个 Sample。
- 不同 Zone 的 `note` 范围不允许重叠；若存在 velocity 分层，必须保证同一 note 在不同 velocity 区间唯一命中。
- 对于打击乐 Zone，必须满足 `min_note == max_note`，且 `flags` 通常设置为 `ZONE_FLAG_PERCUSSION | ZONE_FLAG_POLY_RETRIGGER`。
- 对于旋律 Zone，通常满足 `min_note < max_note`，且 `flags` 通常设置为 `ZONE_FLAG_MELODIC | ZONE_FLAG_POLY_MULTI`。
- `pitch_cents` 限制在 ±100 cents；超出该范围的值下位机应饱和处理。
- **复音策略在 Zone 级别定义**：同一个 Note 被再次触发时，根据 `flags` 的 bit2~7 决定分配新 Voice、重触发原 Voice 还是 Legato 复用。

**典型 Zone flags 组合**：

| 乐器类型 | flags 值 | 含义 |
|---|---|---|
| 钢琴 | `0x15` | melodic + multi + 最多 2 个同音 |
| 鼓 | `0x00` | percussion + retrigger + 最多 1 个同音 |
| 吉他滑音 | `0x09` | melodic + legato + 最多 1 个同音 |

计算 `max_same_note_voices = ((flags & 0xF0) >> 4) + 1`。

### 3.4 Sample Entry（32 bytes）

```c
typedef struct __attribute__((packed)) {
    uint32_t data_offset;       // 相对于采样数据区起始的字节偏移
    uint32_t data_size;         // 字节数，必须为偶数（16-bit 采样）
    uint32_t sample_rate;       // 采样自身采样率（允许与全局不同）
    uint32_t loop_start;        // 循环起始样本偏移（以 sample frame 为单位，从 0 开始）
    uint32_t loop_end;          // 循环结束样本偏移（以 sample frame 为单位，左闭右开）
    uint16_t num_channels;      // 1 = Mono，2 = Stereo（当前仅支持 1）
    uint8_t  bits_per_sample;   // 16
    uint8_t  root_note;         // 采样原始 MIDI 根音（供引擎计算 rootFreq）
    char     name[8];           // 短名，如 "PIANO_C4"
} WavePackSample;
```

**Loop 判定规则**：

```c
bool has_loop = (sp->loop_end > sp->loop_start) && (sp->loop_end > 0);
```

- `loop_end == 0` 视为不循环。
- `loop_end <= loop_start` 视为不循环。
- 循环区间以 sample frame 为单位，不包含 `loop_end` 本身（即左闭右开）。
- 例如：一个 10000 frame 的采样，若希望全程循环，则 `loop_start = 0`，`loop_end = 10000`。

### 3.5 PCM 数据区

- **格式**：有符号 16-bit little-endian mono（s16le）。
- **声道**：立体声 WAV 必须在上位机混缩为单声道；推荐混缩公式为 `(L + R) // 2`。
- **对齐**：每个采样 PCM 块末尾补零到 4 bytes 倍数；整个 PCM 区起始按 4096 bytes 对齐。
- **顺序**：按 Sample Directory 中条目顺序连续存放。

### 3.6 设计要点

- **Zone 与 Sample 解耦**：多个 Zone（力度层、音域重叠）可指向同一个 Sample，节省空间。
- **鼓机复用同一套查找逻辑**：不需要独立的 pad_id 或 drum map 表；鼓组 Zone 的 note 范围收缩为单个 GM Drum Note 即可。
- **4KB 对齐**：`data_offset` 对齐到 Flash page，便于 ESP32 内存映射或 DMA 直接读取。
- **纯 s16le mono**：当前 WavePack 仅输出 16-bit mono；引擎原生支持 4/8/16-bit，若后续版本需要降低 Flash 占用，可扩展 `bits_per_sample` 与 `flags`。

---

## 4. 下位机消费模型

下位机加载 `.wavepack` 后，按以下方式消费数据：

1. 读取 Header，校验 `magic`、`version`、`crc32`。
2. 将 Zone Directory 与 Sample Directory 加载到内部 SRAM。
3. 将 Sample Data 加载到 PSRAM（或保持内存映射）。
4. 收到 `NOTE_ON` 时，通过 `(note, velocity)` 在 Zone Directory 中命中唯一 Zone。
5. 根据 Zone 指向的 Sample 与 `flags` 触发 Voice。

### 4.1 MIDI Note → CentiHz 查表

下位机需要 `MIDI_TO_CENTIHZ_LUT[128]`，用于：

- 把 `WavePackSample.root_note` 转换为 `SampleData.rootFreqCentiHz`。
- 把 Zone 的 `min_note/max_note` 转换为 `SampleZone.lowFreq/highFreq`。

计算公式（仅允许在上位机或编译期使用浮点）：

```python
import math
MIDI_TO_CENTIHZ_LUT = [int(round(440.0 * math.pow(2.0, (n - 69) / 12.0) * 100)) for n in range(128)]
```

### 4.2 Cents 比例查表

下位机需要 `CENT_RATIO_LUT[-100..+100]`，用于把 `pitch_cents` 应用到播放速度增量：

```python
import math
CENT_RATIO_LUT = [int(round(math.pow(2.0, c / 1200.0) * 65536)) for c in range(-100, 101)]
```

### 4.3 下位机查找算法示例

```c
const WavePackZone* find_zone(uint8_t note, uint8_t velocity) {
    for (uint16_t i = 0; i < header.num_zones; i++) {
        const WavePackZone* z = &zones[i];
        if (note >= z->min_note && note <= z->max_note &&
            velocity >= z->min_vel && velocity <= z->max_vel) {
            return z;
        }
    }
    return NULL;
}
```

对于力度分层，必须保证同一 `(note, velocity)` 不会命中多个 Zone。

---

## 5. 上位机工具链

### 5.1 设计原则

- **命令行为主，GUI 可选**：优先保证命令行打包器可用；可视化编辑器作为第二阶段增强。
- **输入驱动**：一个 JSON 描述文件 + 若干 WAV 文件 → 一个 `.wavepack`。
- **输出自解释**：`.wavepack` 文件不依赖外部元数据即可被下位机完整解析。

### 5.2 目录约定

```
/sdcard/wavepack/          # 下位机运行时目录
  piano_acoustic.wavepack
  piano_electric.wavepack
  drum_standard.wavepack

tools/wavepack/            # 上位机工具目录
  pack.py                  # JSON + WAV → .wavepack
  validate.py              # 校验 .wavepack 结构
  gen_lut.py               # 生成 centihz_lut.h / cent_ratio_lut.h
```

### 5.3 pack.json 输入格式

```json
{
  "name": "Acoustic Piano",
  "sample_rate": 44100,
  "zones": [
    {
      "file": "piano_c2.wav",
      "root_note": 36,
      "loop_start": 0,
      "loop_end": 0,
      "min_note": 0,
      "max_note": 43,
      "min_vel": 0,
      "max_vel": 127,
      "flags": 21,
      "adsr": [5, 1500, 0, 120],
      "pitch_cents": 0
    },
    {
      "file": "piano_c4.wav",
      "root_note": 60,
      "loop_start": 0,
      "loop_end": 0,
      "min_note": 44,
      "max_note": 67,
      "min_vel": 0,
      "max_vel": 127,
      "flags": 21,
      "adsr": [5, 1200, 0, 120],
      "pitch_cents": 0
    },
    {
      "file": "piano_c6.wav",
      "root_note": 84,
      "loop_start": 0,
      "loop_end": 0,
      "min_note": 68,
      "max_note": 96,
      "min_vel": 0,
      "max_vel": 127,
      "flags": 21,
      "adsr": [5, 1000, 0, 120],
      "pitch_cents": 0
    }
  ]
}
```

**鼓组示例**：

```json
{
  "name": "Standard Drum Kit",
  "sample_rate": 44100,
  "zones": [
    {
      "file": "kick.wav",
      "root_note": 36,
      "min_note": 36,
      "max_note": 36,
      "flags": 0,
      "adsr": [1, 200, 0, 200]
    },
    {
      "file": "snare.wav",
      "root_note": 38,
      "min_note": 38,
      "max_note": 38,
      "flags": 0,
      "adsr": [1, 100, 0, 300]
    },
    {
      "file": "hihat_c.wav",
      "root_note": 42,
      "min_note": 42,
      "max_note": 42,
      "flags": 0,
      "adsr": [1, 50, 0, 100]
    },
    {
      "file": "hihat_o.wav",
      "root_note": 46,
      "min_note": 46,
      "max_note": 46,
      "flags": 0,
      "adsr": [1, 80, 0, 150]
    }
  ]
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | 是 | 音色名称，仅用于上位机展示 |
| `sample_rate` | int | 是 | 全局采样率，通常 44100 |
| `zones` | array | 是 | Zone 列表；每个 Zone 自带 `file` 与采样元数据 |
| `zones[].file` | string | 是 | WAV 文件路径（相对 pack.json 目录） |
| `zones[].root_note` | int | 是 | 采样原始 MIDI 根音，决定播放速度基准 |
| `zones[].loop_start` | int | 否 | 循环起始样本偏移，默认 0 |
| `zones[].loop_end` | int | 否 | 循环结束样本偏移（左闭右开），默认 0 |
| `zones[].min_note` | int | 是 | 音域下限 |
| `zones[].max_note` | int | 是 | 音域上限 |
| `zones[].min_vel` | int | 否 | 默认 0 |
| `zones[].max_vel` | int | 否 | 默认 127 |
| `zones[].flags` | int | 否 | 默认 21（melodic + multi + 最多 2 同音） |
| `zones[].poly_mode` | string | 否 | `"retrigger"` / `"multi"` / `"legato"`，打包器据此计算 flags |
| `zones[].max_same_note_voices` | int | 否 | 同音最大 Voice 数，默认 2（multi）/ 1（retrigger、legato） |
| `zones[].adsr` | array | 否 | 默认 `[0, 0, 255, 0]`，单位为 `[ms, ms, level_0_255, ms]` |
| `zones[].pitch_cents` | int | 否 | 默认 0，范围 -100~+100 |

**推荐 `poly_mode` 配置**：

| 乐器 | `poly_mode` | `max_same_note_voices` |
|---|---|---|
| 钢琴 | `multi` | 2~3 |
| 鼓 | `retrigger` | 1 |
| 吉他滑音 | `legato` | 1 |
| 弦乐 | `multi` | 2 |
| 管乐 | `multi` | 1 |

### 5.4 Python 核心打包逻辑

```python
import struct
import wave
import json
import os
import math
from pathlib import Path

WAVEPACK_VERSION = 0x0101

ZONE_FLAG_PERCUSSION = 0x00
ZONE_FLAG_MELODIC = 0x01
ZONE_FLAG_LOOP = 0x02
ZONE_FLAG_POLY_RETRIGGER = 0x00
ZONE_FLAG_POLY_MULTI = 0x04
ZONE_FLAG_POLY_LEGATO = 0x08


class WavePackBuilder:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.zones = []
        self.samples = []
        self.pcm_data = bytearray()

    def _add_sample(self, wav_path, root_note, loop_start=0, loop_end=0, name=""):
        """读取 WAV 并注册一个 Sample；返回 sample_idx。"""
        with wave.open(str(wav_path), 'rb') as wf:
            nch = wf.getnchannels()
            sw = wf.getsampwidth()
            fr = wf.getframerate()
            nframes = wf.getnframes()
            raw = wf.readframes(nframes)

            import array
            if sw == 2 and nch == 2:
                stereo = array.array('h', raw)
                mono = array.array('h', [(stereo[i*2] + stereo[i*2+1]) // 2
                                          for i in range(nframes)])
                pcm = mono.tobytes()
            elif sw == 2 and nch == 1:
                pcm = raw
            else:
                raise ValueError("Only 16bit WAV supported (mono or stereo)")

        # 4 字节对齐
        while len(pcm) % 4 != 0:
            pcm += b'\x00'

        sample_idx = len(self.samples)
        data_offset = len(self.pcm_data)

        short_name = name.encode('ascii')[:8].ljust(8, b'\x00')
        if not name:
            short_name = Path(wav_path).stem[:8].encode('ascii').ljust(8, b'\x00')

        self.samples.append({
            'data_offset': data_offset,
            'data_size': len(pcm),
            'sample_rate': fr,
            'root_note': root_note,
            'loop_start': loop_start,
            'loop_end': loop_end,
            'channels': 1,
            'bits': 16,
            'name': short_name,
        })

        self.pcm_data += pcm
        return sample_idx

    def _encode_flags(self, min_note, max_note, poly_mode, max_same_note_voices, force_loop=False):
        melodic_bit = ZONE_FLAG_MELODIC if min_note < max_note else ZONE_FLAG_PERCUSSION
        if poly_mode == "multi":
            mode_bit = ZONE_FLAG_POLY_MULTI
        elif poly_mode == "legato":
            mode_bit = ZONE_FLAG_POLY_LEGATO
        else:  # retrigger
            mode_bit = ZONE_FLAG_POLY_RETRIGGER
        max_same = max(1, min(16, max_same_note_voices)) - 1
        flags = melodic_bit | mode_bit | (max_same << 4)
        if force_loop:
            flags |= ZONE_FLAG_LOOP
        return flags

    def add_zone(self, wav_path, root_note, min_note, max_note,
                 loop_start=0, loop_end=0,
                 min_vel=0, max_vel=127, flags=None,
                 poly_mode="multi", max_same_note_voices=2,
                 adsr=(0, 0, 255, 0), pitch_cents=0, name=""):
        """读取 WAV 并绑定到指定 note/velocity 范围。"""
        sample_idx = self._add_sample(wav_path, root_note, loop_start, loop_end, name)

        if flags is None:
            force_loop = (loop_end > loop_start) and (loop_end > 0)
            flags = self._encode_flags(min_note, max_note, poly_mode,
                                       max_same_note_voices, force_loop)

        self.zones.append({
            'zone_id': len(self.zones),
            'sample_idx': sample_idx,
            'min_note': min_note,
            'max_note': max_note,
            'min_vel': min_vel,
            'max_vel': max_vel,
            'flags': flags,
            'attack_ms': adsr[0],
            'decay_ms': adsr[1],
            'sustain_level': adsr[2],
            'release_ms': adsr[3],
            'pitch_cents': max(-100, min(100, pitch_cents)),
            'filter_cutoff': 0,
            'filter_resonance': 0,
            'reverb_send': 0,
        })

    def load_json(self, json_path):
        """从 pack.json 加载；每个 Zone 自带 file，无需顶层 samples。"""
        with open(json_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        self.sample_rate = cfg.get('sample_rate', self.sample_rate)
        base = Path(json_path).parent

        for z in cfg.get('zones', []):
            wav = base / z['file']
            flags = z.get('flags')
            poly_mode = z.get('poly_mode', 'multi')
            max_voices = z.get('max_same_note_voices',
                               2 if poly_mode == 'multi' else 1)
            if flags is None:
                force_loop = (z.get('loop_end', 0) > z.get('loop_start', 0))
                flags = self._encode_flags(z['min_note'], z['max_note'],
                                           poly_mode, max_voices, force_loop)

            self.add_zone(
                wav_path=wav,
                root_note=z['root_note'],
                min_note=z['min_note'],
                max_note=z['max_note'],
                loop_start=z.get('loop_start', 0),
                loop_end=z.get('loop_end', 0),
                min_vel=z.get('min_vel', 0),
                max_vel=z.get('max_vel', 127),
                flags=flags,
                adsr=z.get('adsr', (0, 0, 255, 0)),
                pitch_cents=z.get('pitch_cents', 0),
                name=z.get('name', ''),
            )

    def build(self, output_path):
        header_size = 64
        zone_size = len(self.zones) * 48
        sample_dir_size = len(self.samples) * 32
        data_offset_base = header_size + zone_size + sample_dir_size
        padding = (4096 - (data_offset_base % 4096)) % 4096
        data_offset = data_offset_base + padding

        with open(output_path, 'wb') as f:
            # Header
            f.write(b'WAVEPACK')
            f.write(struct.pack('<HHHH',
                                WAVEPACK_VERSION,
                                len(self.zones),
                                len(self.samples),
                                0x0001))
            f.write(struct.pack('<IIII',
                                64,
                                64 + zone_size,
                                data_offset,
                                len(self.pcm_data)))
            f.write(struct.pack('<I', self.sample_rate))
            f.write(b'\x00' * 24)      # reserved[6]
            f.write(struct.pack('<I', 0))  # crc32（可选，当前填 0）

            # Zones
            for z in self.zones:
                f.write(struct.pack('<BBBBBBBB',
                                    z['zone_id'], z['sample_idx'],
                                    z['min_note'], z['max_note'], z['min_vel'], z['max_vel'],
                                    z['flags'], 0))  # reserved0
                f.write(struct.pack('<HHHHhHHH',
                                    z['attack_ms'], z['decay_ms'], z['sustain_level'], z['release_ms'],
                                    z['pitch_cents'], z['filter_cutoff'], z['filter_resonance'],
                                    z['reverb_send']))
                f.write(b'\x00' * 24)  # reserved[6]

            # Samples
            for s in self.samples:
                f.write(struct.pack('<IIIII',
                                    s['data_offset'], s['data_size'], s['sample_rate'],
                                    s['loop_start'], s['loop_end']))
                f.write(struct.pack('<HBB', s['channels'], s['bits'], s['root_note']))
                f.write(s['name'])

            # Padding + Data
            f.write(b'\x00' * padding)
            f.write(self.pcm_data)

        print(f"Built: {len(self.zones)} zones, {len(self.samples)} samples, "
              f"{len(self.pcm_data)} bytes PCM -> {output_path}")


# 使用示例
builder = WavePackBuilder(sample_rate=44100)

# 钢琴：multi 模式，最多 2 个同音
builder.add_zone("piano_c2.wav", root_note=36, min_note=0,  max_note=43,
                 poly_mode="multi", max_same_note_voices=2,
                 adsr=(5, 1500, 0, 120))
builder.add_zone("piano_c4.wav", root_note=60, min_note=44, max_note=67,
                 poly_mode="multi", max_same_note_voices=2,
                 adsr=(5, 1200, 0, 120))
builder.add_zone("piano_c6.wav", root_note=84, min_note=68, max_note=96,
                 poly_mode="multi", max_same_note_voices=2,
                 adsr=(5, 1000, 0, 120))

# 鼓组：retrigger 模式
builder.add_zone("kick.wav",   root_note=36, min_note=36, max_note=36,
                 poly_mode="retrigger", adsr=(1, 200, 0, 200))
builder.add_zone("snare.wav",  root_note=38, min_note=38, max_note=38,
                 poly_mode="retrigger", adsr=(1, 100, 0, 300))
builder.add_zone("hihat_c.wav", root_note=42, min_note=42, max_note=42,
                 poly_mode="retrigger", adsr=(1, 50, 0, 100))

builder.build("piano_kit.wavepack")
```

### 5.5 CentiHz 与 Cents 比例查表生成

下位机渲染时需要 MIDI note → 频率、以及 cents → 频率比例的查表。上位机工具链可提供脚本生成这些头文件，供下位机编译时嵌入：

```python
import math

def generate_centihz_lut(path="centihz_lut.h"):
    lut = []
    for n in range(128):
        hz = 440.0 * math.pow(2.0, (n - 69) / 12.0)
        lut.append(int(round(hz * 100)))

    with open(path, "w") as f:
        f.write("#ifndef MIDI_TO_CENTIHZ_LUT_H\n")
        f.write("#define MIDI_TO_CENTIHZ_LUT_H\n\n")
        f.write("#include <stdint.h>\n\n")
        f.write("static const uint32_t MIDI_TO_CENTIHZ_LUT[128] = {\n")
        f.write(", ".join(str(x) for x in lut))
        f.write("\n};\n\n")
        f.write("#endif /* MIDI_TO_CENTIHZ_LUT_H */\n")

def generate_cent_ratio_lut(path="cent_ratio_lut.h"):
    lut = []
    for c in range(-100, 101):
        ratio = math.pow(2.0, c / 1200.0)
        q16 = int(round(ratio * 65536))
        lut.append(q16)

    with open(path, "w") as f:
        f.write("#ifndef CENT_RATIO_LUT_H\n")
        f.write("#define CENT_RATIO_LUT_H\n\n")
        f.write("#include <stdint.h>\n\n")
        f.write("static const uint32_t CENT_RATIO_LUT[201] = {\n")
        f.write(", ".join(str(x) for x in lut))
        f.write("\n};\n\n")
        f.write("#endif /* CENT_RATIO_LUT_H */\n")
```

---

## 6. 校验清单（上位机生成后必须检查）

1. `magic` 为 `"WAVEPACK"`。
2. `version` 为 `0x0101`.
3. `num_zones > 0` 且 `num_samples > 0`。
4. 每个 Zone 的 `sample_idx < num_samples`。
5. 每个 Zone 的 `min_note <= max_note` 且 `min_vel <= max_vel`。
6. 不同 Zone 的 `note` 范围不允许重叠；若使用 velocity 分层，必须保证同一 `(note, velocity)` 唯一命中。
7. 每个 Sample 的 `data_offset + data_size <= data_size_total`。
8. 每个 Sample 的 `data_size` 为偶数。
9. `data_offset` 按 4096 对齐。
10. 对于 percussion Zone：`min_note == max_note`。
11. 对于 melodic Zone：`min_note < max_note`。
12. Zone `flags` 的 bit2~3 必须为 0x00、0x04 或 0x08 之一。
13. Zone `flags` 的 bit4~7 为 `max_same_note_voices - 1`，打包器应确保该值符合乐器特性（如钢琴 1~2，鼓 0）。

---

## 7. 与官方 `WavToEsp32SynthConverter.py` 的差异

ESP32Synth 官方提供的 `tools/Samples/WavToEsp32SynthConverter.py` 是一个轻量级 PyQt6 小工具，用于把单个 WAV 转换为 C/C++ 头文件数组，与 WavePack Maker 的定位不同。主要差异如下：

| 维度 | 官方 `WavToEsp32SynthConverter.py` | WavePack Maker v1.1 |
|---|---|---|
| 输出形态 | 单个 `.h` 头文件，C 数组常量 | `.wavepack` 二进制文件 |
| 使用场景 | 编译期把采样烧录进 Flash | 运行期从 SD/PSRAM 加载 |
| 根音来源 | 硬编码 `c4`（26163 centiHz） | `Sample.root_note`（MIDI），下位机查表转换 |
| Zone 命中 | 按频率范围 `lowFreq/highFreq` | 按 `(note, velocity)`，加载器再转 centiHz |
| 力度分层 | 不支持 | 支持 |
| ADSR / Filter / Reverb / Pitch cents | 不支持 | Zone Entry 携带 |
| Loop 归属 | `Instrument_Sample` 乐器级 | `Sample Entry` 采样级；Zone flags 可强制循环 |
| 位深 | 支持 16/8/4-bit | 当前仅 16-bit mono |
| 立体声处理 | `np.mean` 平均为单声道 | `(L + R) // 2` 平均为单声道 |

**重要兼容性提示**：

1. 官方脚本在 `loop_end >= 采样长度` 时会强制把 `loop_end` 置 0，而 WavePack 允许 `loop_end == total_frames` 表示全程循环。下位机解析 `.wavepack` 时应遵循本规范。
2. 官方脚本的根音单位是 centiHz，WavePack 使用 MIDI note。下位机必须通过 `MIDI_TO_CENTIHZ_LUT` 转换后再调用 `registerSample()`，不可直接把 `root_note` 当 centiHz 使用。
3. 官方脚本生成的 `SampleZone.rootOverride` 为 `c4`，WavePack 下位机加载器应将其置 0，避免覆盖 `SampleData.rootFreqCentiHz`。

---

## 8. 命名建议

| 项目 | 建议命名 | 示例 |
|---|---|---|
| 钢琴包 | `{instrument}_{variant}.wavepack` | `piano_acoustic.wavepack` |
| 鼓组包 | `drum_{kit_name}.wavepack` | `drum_standard.wavepack` |
| 音色目录 | `/sdcard/wavepack/` | — |
| LUT 头文件 | `wavepack_lut.h` | 同时包含 CentiHz 与 CentRatio |

---

## 9. 附录：版本变更

### 当前修订（2026-07-11）

- 修正文档内部版本号不一致问题（标题、Header 注释、校验清单统一为 v1.1 / `0x0101`）。
- 新增第 2 节"与 ESP32Synth 引擎的关系"，明确 `.wavepack` 与引擎原生 `SampleData` / `SampleZone` / `Instrument_Sample` 的映射关系。
- 新增第 4 节"下位机消费模型"，细化加载器职责、MIDI→CentiHz 查表、查找算法示例。
- 新增第 7 节"与官方 `WavToEsp32SynthConverter.py` 的差异"。
- 修正 `pack.json` 输入格式：删除顶层 `samples[]`，每个 Zone 自带 `file`；与当前打包器实现保持一致。
- 修正默认 ADSR 为 `[0, 0, 255, 0]`，与当前打包器实现保持一致。
- 明确当前 WavePack 仅支持 16-bit mono；引擎原生支持 4/8/16-bit，后续版本可扩展。
- 明确 `SampleZone.rootOverride` 应由下位机加载器置 0。

### v1.1（2026-07-10）

- 二进制 `version` 字段升级为 `0x0101`。
- 删除 `WavePackZone.root_note` 字段：Zone 查找仅由 `min_note/max_note` 与 `min_vel/max_vel` 决定。
- Pitch 根音唯一来源为 `WavePackSample.root_note`：Melodic Zone 按目标 note 对 Sample 做 pitch shift；Percussion Zone 固定按 `Sample.root_note` 播放。
- 约束前提：不同 Zone 的 `note` 范围不允许重叠；一个 Zone 绑定一个 Sample。

### v1.0（2026-07-08）

- 首个正式版本，二进制 `version` 字段统一为 `0x0100`。
- 一个 `.wavepack` 文件代表一个音色，内部统一按 note + velocity 查找 Zone。
- 复音策略（retrigger/multi/legato）在 Zone `flags` 中定义。
- 鼓组与键盘共用同一套查找逻辑。
- MIDI Channel、Program Change、乐理元数据、现场采样均为 WavePack 格式之外的关注点。
