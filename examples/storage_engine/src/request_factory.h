/// request_factory.h — RequestFactory: creates IoRequest instances.

#pragma once
#include "nvme_controller.h"

namespace storage {

/// RequestFactory: constructs IoRequest objects with validated parameters.
class RequestFactory {
    int default_len_ = 512;

public:
    IoRequest makeRead (int lba, char*       buf, int len = 0);
    IoRequest makeWrite(int lba, const char* buf, int len = 0);
    void      setDefaultLen(int len);
};

} // namespace storage
