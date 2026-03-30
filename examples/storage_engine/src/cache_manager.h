/// cache_manager.h — CacheManager: generic LRU key-value cache.

#pragma once
#include <unordered_map>
#include <list>
#include <stdexcept>

namespace storage {

/// CacheManager: provides LRU key-value caching with configurable capacity.
template<typename K, typename V>
class CacheManager {
    size_t                                      capacity_;
    std::list<std::pair<K,V>>                   lru_list_;
    std::unordered_map<K, typename std::list<std::pair<K,V>>::iterator> index_;

public:
    explicit CacheManager(size_t capacity = 256) : capacity_(capacity) {}

    void put(const K& key, const V& val);
    V    get(const K& key);
    void evict(const K& key);
    bool contains(const K& key) const;
    size_t size() const { return index_.size(); }
    void   clear();
};

} // namespace storage
