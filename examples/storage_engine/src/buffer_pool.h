/// buffer_pool.h — BufferPool: manages a fixed-size DMA-capable memory pool.

#pragma once
#include <cstddef>
#include <vector>

namespace storage {

/// BufferPool: allocates and releases fixed-size DMA buffers.
class BufferPool {
    std::vector<char*> free_list_;
    size_t             block_size_;
    size_t             capacity_;

public:
    explicit BufferPool(size_t block_size = 512, size_t capacity = 64);
    ~BufferPool();

    char* allocate(int size);
    void  release(char* ptr);

    size_t freeCount()  const;
    size_t totalCount() const { return capacity_; }
};

} // namespace storage
