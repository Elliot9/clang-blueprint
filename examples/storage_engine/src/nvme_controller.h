/// nvme_controller.h — NVMeController: orchestrates NVMe submission/completion queues.

#pragma once
#include <memory>
#include <queue>
#include "nvme_driver.h"

namespace storage {

struct IoRequest {
    int   lba;
    char* buf;
    int   len;
    bool  is_write;
};

/// NVMeController: manages NVMe I/O submission and completion queues.
/// Aggregation: NVMeDriver* (raw pointer, externally owned)
class NVMeController {
    NVMeDriver*              drv_;       // aggregation (raw ptr)
    std::queue<IoRequest>    sq_;        // submission queue
    int                      max_depth_  = 64;

public:
    explicit NVMeController(NVMeDriver* drv);

    void submitIO(const IoRequest& req);
    void pollCompletion();
    int  queueDepth() const;
    void flush();
};

} // namespace storage
