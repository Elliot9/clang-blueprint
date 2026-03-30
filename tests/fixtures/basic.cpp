// fixtures/basic.cpp — 基礎測試用 C++ 片段
// 涵蓋：composition, aggregation, inheritance, template, cardinality

#include <memory>
#include <vector>
#include <map>
#include <string>

// ── 基底類別 ──────────────────────────────────────────────
class IoBase {
public:
    virtual void open()  = 0;
    virtual void close() = 0;
};

// ── 純粹被依賴類別 ────────────────────────────────────────
class NVMeDriver {
public:
    void init();
    void shutdown();
};

class BufferPool {
public:
    char* allocate(int size);
    void  release(char* ptr);
};

// ── 主要測試目標：DiskManager ─────────────────────────────
//
// 預期解析結果：
//   composition  → NVMeDriver  (unique_ptr 成員)
//   aggregation  → BufferPool  (shared_ptr 成員)
//   inheritance  → IoBase
//   cardinality  → std::vector<int>  → 1..*
class DiskManager : public IoBase {
    std::unique_ptr<NVMeDriver>  driver_;   // composition
    std::shared_ptr<BufferPool>  buf_pool_; // aggregation
    std::vector<int>             lba_map_;  // cardinality 1..*

public:
    void open()  override;
    void close() override;
    void readBlock(int lba, char* buf);
    void writeBlock(int lba, const char* buf);
};

// ── Template 測試目標 ─────────────────────────────────────
template<typename K, typename V>
class CacheManager {
    std::map<K, V> store_;
public:
    void   put(const K& key, const V& val);
    V      get(const K& key);
    void   evict(const K& key);
};

// ── FSM 測試目標 ──────────────────────────────────────────
enum class DriveState { Idle, Reading, Writing, Error };

class DriveController {
    DriveState state_ = DriveState::Idle;
    NVMeDriver* drv_;  // raw ptr → aggregation
public:
    void handleEvent(int event);
    DriveState getState() const;
};
