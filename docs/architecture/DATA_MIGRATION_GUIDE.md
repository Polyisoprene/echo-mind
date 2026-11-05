# EchoMind 外部数据导入与旧版迁移开发指南
**（Data Import & Custom Migration Developer Guide）**

> **设计原则**：`EchoMind` 核心源码（`src/echomind/`）保持 100% 通用与纯粹，**内置零个人硬编码数据、且不耦合任何特定旧框架的私有插件 JSON 格式**。
> 当你需要从旧版机器人（如 `qq-agent`、`AstrBot`、`Koishi` 或自定义 JSON/数据库）迁移历史数据时，只需参照本文档调用 `EchoMind` 的标准仓储接口编写一个独立迁移脚本（参考 `tools_migration/migrate_qq_agent.py`）。

---

## 一、 目标数据库架构规范（`data/echomind.db` · SQLite WAL）

`EchoMind` 启动或调用 `await SqliteDatabase(db_path).initialize()` 时，会自动初始化以下核心表。你的自定义迁移工具只需向这些表写入标准领域对象：

### 1. `social_bonds`（群友/好友关系、好感度、性格画像与防骗可信度）
- **主键**：`PRIMARY KEY (chat_key, user_id)`（支持幂等 `ON CONFLICT DO UPDATE`）
- **标准写入接口**：`await memory_repo.upsert_social_bond(SocialBondProfile(...))`
- **字段契约**：
  | 字段名 | 类型与范围 | 说明 |
  |---|---|---|
  | `chat_key` | `str` | 会话标识，群聊为 `"group:<群号>"`，私聊为 `"private:<QQ号>"` |
  | `user_id` | `str` | 成员唯一账号 ID（如 QQ 号） |
  | `user_name` | `str` | 成员昵称或群名片 |
  | `group_role` | `Literal["owner", "admin", "member"]` | 群内真实权限角色 |
  | `affinity_score` | `float` | 累计好感度分值 |
  | `affinity_level` | `int (0~5)` | 好感等级（0=陌生 ~ 5=挚友） |
  | `msg_count` | `int` | 历史累计互动发言条数 |
  | `trust_score` | `float (0.0~1.0)` | **元认知防忽悠可信度**（operator 可设 `1.0`，普通群友默认 `0.8`，常开玩笑忽悠者可设 `0.4~0.6`） |
  | `is_rival` | `bool` | 是否为占有欲系统的“吃醋警惕对象” |
  | `rival_reason` | `str` | 警惕原因说明 |
  | `traits` | `tuple[str, ...]` | 该成员的长期性格与喜好画像列表 |

### 2. `episodic_memories`（海马体情景记忆事件卡 · 走艾宾浩斯遗忘曲线）
- **标准写入接口**：`await memory_repo.save_episodic_card(EpisodicCard(...))`
- **字段契约**：
  | 字段名 | 类型与范围 | 说明 |
  |---|---|---|
  | `chat_key` | `str` | 发生该事件的会话标识（`"group:..."` 或 `"private:..."`） |
  | `timestamp_ms` | `int` | 事件发生时的毫秒级时间戳 |
  | `summary` | `str` | **核心事件总结**（20~100字，交代谁、起因、经过、结果，严禁只存单句碎话） |
  | `key_detail` | `str` | **关键细节锚点**（具体数字、暗号、约定、进度等不可丢失的硬细节，控制在 45 字内） |
  | `participants` | `tuple[str, ...]` | 参与该事件的成员昵称或账号元组 |
  | `importance` | `float (1.0~5.0)` | 重要度评分（决定艾宾浩斯初始半衰期长短） |
  | `pinned` | `bool` | 是否作为核心永久记忆置顶 |
  | `rehearsals` | `int` | 历史被提及复习的次数 |

### 3. `semantic_facts`（语义事实与元认知防忽悠权威底表）
- **唯一约束**：`UNIQUE (chat_key, subject)`
- **标准写入接口**：`await memory_repo.upsert_semantic_fact(SemanticFact(...))`
- **字段契约**：
  | 字段名 | 类型与范围 | 说明 |
  |---|---|---|
  | `chat_key` | `str` | 作用域会话标识 |
  | `subject` | `str` | 事实主语/主题（如 `"本群真实群主"`、`"当前 operator"`） |
  | `fact_text` | `str` | 客观事实陈述 |
  | `confidence` | `float (0.0~1.0)` | 事实置信度 |
  | `is_locked` | `bool` | **防忽悠锁**：设为 `True` 时，任何群友口头忽悠（`source="peer"`）均会被仓储层自动拦截拒绝覆盖 |
  | `source` | `Literal["system", "owner", "explored", "peer"]` | 事实来源（系统权威 / **operator 亲授**（字段名沿用 `owner`）/ 自主搜索 / 群友自述） |

### 4. `procedural_rules`（程序性条件反射与专属默契表）
- **唯一约束**：`UNIQUE (chat_key, trigger_keyword, trigger_user_id)`
- **标准写入接口**：`await memory_repo.upsert_procedural_rule(ProceduralRule(...))`
- **字段契约**：
  - `trigger_keyword: str`（触发关键词，如小名、外号）
  - `trigger_user_id: str`（限定触发人 ID，空字符串 `""` 表示任何人触发均生效）
  - `action_instruction: str`（命中后注入工作记忆的条件反射指令）
  - `strength: int (1~10)`（反射强度）

### 5. `working_state` & `plastic_params`（工作记忆快照与可塑参数）
- **标准写入接口**：
  - `await working_repo.save_working_state(WorkingSnapshot(...))`
  - `await working_repo.ensure_default_params()`

---

## 二、 通用自定义迁移脚本编写模板（50 行极简范例）

任何开发者只需在 `tools_migration/` 下新建一个脚本，按如下标准模式即可把自己的旧数据导入 `EchoMind`：

```python
import asyncio
from pathlib import Path
from echomind.adapters.storage.database import SqliteDatabase
from echomind.adapters.storage.memory_repo import SqliteMemoryRepository
from echomind.adapters.storage.working_repo import SqliteWorkingStateStore
from echomind.domain.models import EpisodicCard, SemanticFact, SocialBondProfile


async def run_custom_migration() -> None:
    # 1. 初始化 SQLite WAL 数据库与标准仓储
    db = SqliteDatabase(Path("data/echomind.db"))
    await db.initialize()
    mem_repo = SqliteMemoryRepository(db)
    work_repo = SqliteWorkingStateStore(db)
    await work_repo.ensure_default_params()

    # 2. 导入权威防忽悠事实（is_locked=True 防止群友忽悠篡改）
    await mem_repo.upsert_semantic_fact(
        SemanticFact(
            chat_key="group:你的群号",
            subject="本群真实群主",
            fact_text="本群群主是 XXX (QQ:123456)",
            confidence=1.0,
            is_locked=True,
            source="system",
        )
    )

    # 3. 导入群友好感度与性格画像
    await mem_repo.upsert_social_bond(
        SocialBondProfile(
            chat_key="group:你的群号",
            user_id="群友QQ",
            user_name="群友昵称",
            group_role="member",
            affinity_score=85.0,
            affinity_level=3,
            trust_score=0.85,
            traits=("喜欢聊二次元", "说话幽默"),
        )
    )

    # 4. 导入历史事件记忆卡片
    await mem_repo.save_episodic_card(
        EpisodicCard(
            chat_key="group:你的群号",
            timestamp_ms=1793160000000,
            summary="和群友一起讨论了新番剧情并约好周末一起看",
            key_detail="约好周六晚8点看新番",
            participants=("群友QQ",),
            importance=3.5,
        )
    )


if __name__ == "__main__":
    asyncio.run(run_custom_migration())
```

---

## 三、 本机专用旧版 `qq-agent/data-2` 迁移工具用法

针对本机原有的 `qq-agent`（含 `affinity`、`ebbinghaus-memory`、`her-life`、`possessive-heart` 插件数据），我们提供了独立于核心源码之外的专用迁移工具 `tools_migration/migrate_qq_agent.py`：

```bash
uv run python tools_migration/migrate_qq_agent.py \
  --legacy-dir /home/polyisoprene/Documents/qq-agent/data-2 \
  --target-db data/echomind.db
```
该工具完全幂等，可重复执行且不会污染 `src/echomind/` 核心代码。

---

## 四、 Stage 29–30 新增表与列（迁移必读）

| 对象 | 变更 | 迁移方式 |
|---|---|---|
| `bond_depth_stats` | 新表：`chat_key, user_id, msgs, her_msgs, replies_to_them, responded_to_her, sessions, impact_sum, impact_n, betrayals, updated_ms` | `SqliteBondDepthStore.ensure_schema()`，可用 `backfill_from_history()` 回填历史 |
| `admin_audit` | 新表：`ts, host, method, path, status` | 写操作中间件自动写入；首次写操作时建表 |
| `social_bonds.bond_depth` | 新列（0~100） | `database.initialize()` 自动 `ALTER TABLE` |
| `persona_traits.chat_key / source / last_used_ms` | 新列 | `storage/migrations.py::ensure_trait_columns()`（幂等） |
| `persona_traits` 类别上限 | habit 8 / taste 4 / temperament 4 / taboo 3 | 运行时裁剪，无需手工迁移 |
| `operatorQq` / `ownerQq` | **已废弃**，配置改用 `operatorIds`（数组或逗号分隔） | 旧键仍会被读取为兼容回退，但不再提供情感特权 |

> ⚠️ 迁移前请先 `VACUUM INTO 'data/backup_pre_migration.db'`；所有新列均为 `NOT NULL DEFAULT`，旧数据自动填充。
