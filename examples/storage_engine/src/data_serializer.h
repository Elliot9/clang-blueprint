/// data_serializer.h — DataSerializer: binary serialization for storage metadata.

#pragma once
#include <vector>
#include <string>
#include <cstdint>

namespace storage {

struct BlockMetadata {
    uint32_t    lba;
    uint32_t    checksum;
    std::string tag;
};

/// DataSerializer: converts BlockMetadata to/from binary format.
class DataSerializer {
public:
    std::vector<uint8_t> serialize(const BlockMetadata& meta);
    BlockMetadata        deserialize(const std::vector<uint8_t>& data);
    bool                 validate(const std::vector<uint8_t>& data);
};

} // namespace storage
