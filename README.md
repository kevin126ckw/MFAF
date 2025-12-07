# 多文件存档格式（MFAF）技术手册 v1.0
**Multi-File Archive Format Specification**

---

## 1. 概述
MFAF 是一种用于将多个文件合并为单一存档文件的二进制格式，支持：
- 任意数量文件
- 可变长度元数据（键值对）
- 快速随机访问
- 完整性校验
- 向前兼容（版本号与预留字段）

---

## 2. 文件整体布局
| 区域 | 偏移 | 长度 | 说明 |
|---|---|---|---|
| 文件头 | 0 | 64 B | 固定长度 |
| 文件内容区 | 64 | 变长 | 所有文件原始字节流顺序拼接 |
| 元数据区 | … | 变长 | 所有文件的元数据序列化块 |
| 文件尾 | 最后 64 B | 64 B | 固定长度 |

> 整个文件大小 = 头 64 B + 内容区长度 + 元数据区长度 + 尾 64 B  
> 头中 `totalSize` 字段必须等于该值。

---

## 3. 字节序与编码
- **字节序**：Little-Endian（x86 惯例）
- **字符串**：UTF-8，无 NUL 终止符；长度前缀显式给出
- **偏移/长度**：`uint64` 最大支持 16 EB 存档

---

## 4. 数据结构定义

### 4.1 文件头（64 B）
| 字段 | 类型 | 偏移 | 长度 | 说明 |
|---|---|---|---|---|
| magic | byte[8] | 0 | 8 | 魔数 `0x4D 41 46 46 49 4C 45 01` ("MAFFILE\x01") |
| totalSize | uint64 | 8 | 8 | 整个存档的字节数 |
| contentOffset | uint64 | 16 | 8 | 文件内容区起始偏移（恒为 64） |
| metadataOffset | uint64 | 24 | 8 | 元数据区起始偏移 |
| fileCount | uint32 | 32 | 4 | 存档内文件数量 |
| version | uint16 | 36 | 2 | 格式主版本（当前 1） |
| flags | uint16 | 38 | 2 | 位标志（0=无压缩，1=全局压缩，保留） |
| reserved | byte[26] | 40 | 26 | 必须填 0x00 |

### 4.2 文件尾（64 B）
| 字段 | 类型 | 偏移* | 长度 | 说明 |
|---|---|---|---|---|
| magic | byte[8] | –64 | 8 | 魔数 `0x45 4E 44 4D 41 46 00 00` ("ENDMAF\x00\x00") |
| metadataEnd | uint64 | –56 | 8 | 元数据区结束偏移（=metadataOffset+元数据长度） |
| checksum | uint32 | –48 | 4 | 元数据区 CRC-32（IEEE 802.3） |
| reserved | byte[52] | –44 | 52 | 必须填 0x00 |

*负偏移相对于文件尾。

---

## 5. 元数据区格式
元数据区为**单个 MessagePack 序列化对象**（高效、二进制、无模式）。

根对象结构（伪代码）：
```json
[
  {
    "n": "file/name.txt",     // 文件名（UTF-8）
    "o": 1234,                // 内容区偏移
    "s": 5678,                // 内容字节数
    "m": "text/plain",        // MIME 类型
    "a": {                    // 扩展属性（可选）
      "ctime": 1700000000,
      "owner": "alice",
      ...
    }
  },
  ...
]
```

- 键全部小写，缺失键按默认值处理（`m` 默认 `application/octet-stream`，`a` 默认 `{}`）
- 属性对象深度 ≤ 3，键长度 ≤ 256，值仅支持 string/int/float/bool/null
- 解码器遇到未知键必须忽略，保证向前兼容

---

## 6. 内容区布局
内容区是**原始文件字节流**的简单拼接，无填充、无压缩（除非 flags 第 0 位=1）。

- 每个文件在内容区仅出现一次
- 偏移与长度由对应元数据项显式给出
- 读取器应验证：  
  `offset + size ≤ metadataOffset`  
  否则视为损坏

---

## 7. 编码流程（参考）
1. 收集待存档文件，计算各自大小
2. 按顺序写入内容区，记录 `(offset, size)`
3. 组装元数据列表，MessagePack 编码
4. 计算 `metadataOffset = 64 + 内容区长度`
5. 计算 `totalSize = metadataOffset + len(metadata) + 64`
6. 写头 → 写内容 → 写元数据 → 写尾
7. 回写尾之前计算 CRC-32（元数据区）

---

## 8. 解码流程（参考）
1. 读取最后 64 B 获取尾魔数与 `metadataEnd`
2. 读取头 64 B 验证魔数与 `totalSize`
3. 验证 `metadataOffset + (metadataEnd - metadataOffset) + 64 == totalSize`
4. 读取 `[metadataOffset, metadataEnd)` 字节，CRC-32 校验
5. MessagePack 解码得到文件列表
6. 按需 seek 到各 `offset` 读取内容

---

## 9. 错误码与异常
| 代码 | 描述 |
|---|---|
| `MFAF_OK` | 成功 |
| `MFAF_ERR_MAGIC` | 魔数不匹配 |
| `MFAF_ERR_SIZE` | 大小字段自相矛盾 |
| `MFAF_ERR_CRC` | 元数据 CRC 失败 |
| `MFAF_ERR_RANGE` | 偏移/长度越界 |
| `MFAF_ERR_MPCK` | MessagePack 解析失败 |
| `MFAF_ERR_VERSION` | 主版本号高于实现支持 |

---

## 10. 扩展指南
- **次要版本升级**：增加新键到元数据对象，保持旧键不变
- **主版本升级**：需修改头/尾结构时，version+1，旧读取器应拒绝
- **压缩扩展**：flags 第 0 位=1 时，内容区为单一 zstd 流，元数据增加 `"z": true` 提示
- **加密扩展**：flags 第 1 位=1 时，内容区与元数据区均为 AES-256-GCM 密文，元数据增加 `"k": "<key-id>"`

---

## 11. 参考实现
官方 MIT 许可参考库：
- C99： `libmfaf-1.0.tar.gz`
- Rust： `mfaf-rs 1.0`
- Python： `pip install mfaf`

---

## 12. 修订历史
| 日期 | 版本 | 说明 |
|---|---|---|
| 2024-11-14 | 1.0 | 首版发布 |

---

## 13. Python 库使用说明

本项目包含一个 Python 库，可用于读取、创建和修改 MFAF 格式的文件。

### 安装

```bash
pip install buttermfaf
```

### 使用方法

#### 创建新的 MFAF 文件

```python
from buttermfaf import MFAFFile, MFAFEntry

# 创建一个新的 MFAF 文件
mfaf = MFAFFile()

# 添加条目
entry1 = MFAFEntry("hello.txt", b"Hello, World!", "text/plain")
entry2 = MFAFEntry("data.bin", b"\x00\x01\x02\x03", "application/octet-stream")

mfaf.add_entry(entry1)
mfaf.add_entry(entry2)

# 保存到文件
mfaf.save("archive.mfaf")
```

#### 从现有文件加载

```python
from buttermfaf import MFAFFile

# 加载现有的 MFAF 文件
mfaf = MFAFFile.load("archive.mfaf")

# 列出所有条目
entries = mfaf.list_entries()
print(entries)  # 输出所有文件名

# 获取特定条目
entry = mfaf.get_entry("hello.txt")
if entry:
    print(entry.content)  # 输出文件内容

# 提取条目到文件系统
mfaf.extract_entry("hello.txt", "extracted_hello.txt")
```

#### 从文件系统添加文件

```python
from buttermfaf import MFAFFile

mfaf = MFAFFile()

# 直接从文件系统添加文件
mfaf.add_file("path/to/myfile.txt", "myfile.txt", "text/plain")

# 保存归档
mfaf.save("archive.mfaf")
```

### API 参考

#### MFAFFile 类

- `MFAFFile()` - 创建新的空 MFAF 归档
- `add_entry(entry: MFAFEntry)` - 添加条目到归档
- `add_file(file_path: str, name: str, mime_type: str, attributes: dict)` - 从文件系统添加文件
- `save(file_path: str)` - 保存归档到文件
- `load(file_path: str) -> MFAFFile` - 从文件加载归档 (类方法)
- `get_entry(name: str) -> MFAFEntry` - 按名称获取条目
- `extract_entry(name: str, output_path: str)` - 提取条目到文件
- `list_entries() -> List[str]` - 列出所有条目名称

#### MFAFEntry 类

- `MFAFEntry(name: str, content: bytes, mime_type: str, attributes: dict)` - 创建新条目
- `name` - 条目名称
- `content` - 条目内容（字节）
- `mime_type` - MIME 类型
- `attributes` - 扩展属性字典
- `offset` - 在归档中的偏移量（内部使用）
- `size` - 条目大小（字节）

---

本手册发布为公共领域，任何实现无需授权，但需自行承担兼容性责任。