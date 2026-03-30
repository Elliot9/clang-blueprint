// fixtures/inheritance.cpp — 多層繼承與多重繼承測試

class Serializable {
public:
    virtual void serialize()   = 0;
    virtual void deserialize() = 0;
};

class Loggable {
public:
    virtual void log(const char* msg) = 0;
};

class StorageEngine : public Serializable, public Loggable {
public:
    void serialize()         override;
    void deserialize()       override;
    void log(const char* msg) override;
    void flush();
};
