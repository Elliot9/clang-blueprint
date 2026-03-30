/// disk_mgr.h — DiskManager: handles low-level disk I/O and partitioning.

#pragma once
#include <memory>
#include <vector>

namespace storage {

class NVMeDriver;
class BufferPool;

/// Abstract I/O interface
class IoBase {
public:
    virtual ~IoBase() = default;
    virtual void open()  = 0;
    virtual void close() = 0;
};

/// DiskManager: manages NVMe block device reads and writes.
/// Composition: NVMeDriver (unique_ptr)
/// Aggregation: BufferPool  (shared_ptr)
class DiskManager : public IoBase {
    std::unique_ptr<NVMeDriver>  driver_;    // composition
    std::shared_ptr<BufferPool>  buf_pool_;  // aggregation
    std::vector<int>             lba_map_;   // cardinality 1..*

public:
    explicit DiskManager(std::shared_ptr<BufferPool> pool);

    void open()  override;
    void close() override;

    void readBlock (int lba, char*       buf);
    void writeBlock(int lba, const char* buf);

    int  getBlockCount() const;
};

} // namespace storage
