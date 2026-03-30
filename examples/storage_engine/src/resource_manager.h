/// resource_manager.h — ResourceManager: lifecycle management for storage resources.

#pragma once
#include <memory>
#include <unordered_map>
#include <string>
#include "disk_mgr.h"
#include "buffer_pool.h"

namespace storage {

/// ResourceManager: manages lifecycle of DiskManager and BufferPool instances.
class ResourceManager {
    std::unordered_map<std::string, std::shared_ptr<DiskManager>> disk_pool_;
    std::shared_ptr<BufferPool>                                    buffer_pool_;

public:
    explicit ResourceManager(std::shared_ptr<BufferPool> pool);

    std::shared_ptr<DiskManager> acquire(const std::string& device_path);
    void                         release(const std::string& device_path);
    void                         releaseAll();
    size_t                       activeCount() const;
};

} // namespace storage
