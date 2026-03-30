/// task_scheduler.h — TaskScheduler: priority queue for async I/O tasks.

#pragma once
#include <functional>
#include <queue>
#include <vector>

namespace storage {

struct Task {
    int                    priority;
    std::function<void()>  fn;
    bool operator<(const Task& o) const { return priority < o.priority; }
};

/// TaskScheduler: schedules and executes background I/O tasks by priority.
class TaskScheduler {
    std::priority_queue<Task> queue_;
    bool                      running_ = false;

public:
    void enqueue(int priority, std::function<void()> fn);
    void run();
    void stop();
    void drain();
    size_t pendingCount() const;
};

} // namespace storage
