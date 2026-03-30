/// event_handler.h — EventHandler: subscribes to and dispatches storage events.

#pragma once
#include <functional>
#include <unordered_map>
#include <vector>
#include <string>

namespace storage {

enum class EventType { ReadComplete, WriteComplete, Error, Timeout };

struct Event {
    EventType   type;
    int         lba;
    std::string message;
};

using EventCallback = std::function<void(const Event&)>;

/// EventHandler: registers callbacks and dispatches storage events.
class EventHandler {
    std::unordered_map<EventType, std::vector<EventCallback>> listeners_;

public:
    void subscribe(EventType type, EventCallback cb);
    void unsubscribe(EventType type);
    void onEvent(const Event& event);
    void dispatch(EventType type, int lba, const std::string& msg = "");
};

} // namespace storage
