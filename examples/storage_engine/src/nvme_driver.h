/// nvme_driver.h — NVMeDriver: hardware abstraction for NVMe devices.

#pragma once

namespace storage {

/// NVMeDriver: provides low-level NVMe command submission and DMA.
class NVMeDriver {
    int  fd_       = -1;
    bool ready_    = false;

public:
    NVMeDriver() = default;
    ~NVMeDriver();

    void init();
    void shutdown();

    void dmaRead (int lba, char*       buf, int len);
    void dmaWrite(int lba, const char* buf, int len);

    bool isReady() const { return ready_; }
};

} // namespace storage
