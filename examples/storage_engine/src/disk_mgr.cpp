/// disk_mgr.cpp — DiskManager: handles low-level disk I/O and partitioning.

#include <memory>
#include <vector>
#include "disk_mgr.h"
#include "nvme_driver.h"
#include "buffer_pool.h"

namespace storage {

void DiskManager::open() {
    driver_->init();
}

void DiskManager::close() {
    driver_->shutdown();
}

void DiskManager::readBlock(int lba, char* buf) {
    char* dma = buf_pool_->allocate(512);
    driver_->dmaRead(lba, dma, 512);
    // copy dma → buf
    buf_pool_->release(dma);
}

void DiskManager::writeBlock(int lba, const char* buf) {
    char* dma = buf_pool_->allocate(512);
    driver_->dmaWrite(lba, dma, 512);
    buf_pool_->release(dma);
}

} // namespace storage
