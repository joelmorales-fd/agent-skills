---
name: resource-leak-detection
description: Detects resource leaks in code reviews and static analysis. Use when reviewing code that creates connections, threads, clients, file handles, or pooled resources. Use when investigating memory leaks, thread exhaustion, connection pool exhaustion, or file descriptor exhaustion. Use when code instantiates external clients inside request handlers or loops.
---

# Resource Leak Detection

## Overview

Detects resource leaks that are invisible in testing but catastrophic in production. These bugs share a common trait:
- Pass all unit tests (mocked dependencies)
- Pass integration tests (short-lived processes)
- Fail only after hours/days of production runtime

**The Pattern:** Creating a resource-backed object (client, connection, thread pool) inside a frequently-called path without proper lifecycle management.

## When to Use

- Reviewing code that creates connections, clients, threads, or file handles
- Investigating production OOM, "too many open files", or thread exhaustion
- After adding new external dependencies (databases, caches, message queues, HTTP clients)
- When code instantiates objects with lifecycle methods (`close()`, `shutdown()`, `dispose()`, `release()`)
- PR review checklist for any code touching I/O or external services
- Post-incident review for resource exhaustion issues

## The Five Resource Leak Patterns

### 1. Per-Request Resource Creation (Most Dangerous)

**Pattern:** Creating a resource-backed object inside a method called per-request/per-iteration.

**Java:**
```java
// BAD: New client per request
public void handleRequest() {
    HttpClient client = HttpClient.newHttpClient();  // Creates threads
    client.send(request, BodyHandlers.ofString());
    // client never closed
}

// GOOD: Reuse client
private static final HttpClient CLIENT = HttpClient.newHttpClient();
public void handleRequest() {
    CLIENT.send(request, BodyHandlers.ofString());
}
```

**Python:**
```python
# BAD: New connection per request
def handle_request():
    conn = psycopg2.connect(DATABASE_URL)  # New TCP connection
    cursor = conn.cursor()
    cursor.execute("SELECT ...")
    # conn never closed

# GOOD: Connection pool
pool = psycopg2.pool.ThreadedConnectionPool(1, 10, DATABASE_URL)
def handle_request():
    conn = pool.getconn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT ...")
    finally:
        pool.putconn(conn)
```

**JavaScript/Node:**
```javascript
// BAD: New client per request
app.get('/data', async (req, res) => {
    const client = new Redis();  // New connection
    const data = await client.get('key');
    res.json(data);
    // client never quit()
});

// GOOD: Shared client
const redis = new Redis();
app.get('/data', async (req, res) => {
    const data = await redis.get('key');
    res.json(data);
});
```

**Go:**
```go
// BAD: New client per request
func handler(w http.ResponseWriter, r *http.Request) {
    client := &http.Client{}  // Creates transport
    resp, _ := client.Get(url)
    // Transport connections leak
}

// GOOD: Reuse client (or use http.DefaultClient)
var client = &http.Client{
    Transport: &http.Transport{MaxIdleConns: 100},
}
func handler(w http.ResponseWriter, r *http.Request) {
    resp, _ := client.Get(url)
    defer resp.Body.Close()
}
```

**Detection Questions:**
- Is this object created inside a loop, request handler, or callback?
- Does the object's type have `close()`, `shutdown()`, `dispose()`, `release()`, or `quit()` methods?
- Does the object manage threads, connections, file handles, or sockets?

### 2. Missing Resource Cleanup (try-with-resources / context managers)

**Pattern:** Resources opened but not guaranteed to close on all paths.

**Java:**
```java
// BAD: Leak on exception
Connection conn = dataSource.getConnection();
Statement stmt = conn.createStatement();
ResultSet rs = stmt.executeQuery("SELECT ...");
// If exception here, connection leaks

// GOOD: Guaranteed cleanup
try (Connection conn = dataSource.getConnection();
     Statement stmt = conn.createStatement();
     ResultSet rs = stmt.executeQuery("SELECT ...")) {
    // process results
}
```

**Python:**
```python
# BAD: Leak on exception
f = open('file.txt')
data = f.read()
process(data)  # If this throws, file never closed
f.close()

# GOOD: Context manager
with open('file.txt') as f:
    data = f.read()
    process(data)
```

**C#:**
```csharp
// BAD
var stream = new FileStream(path, FileMode.Open);
// ...
stream.Close();

// GOOD
using (var stream = new FileStream(path, FileMode.Open))
{
    // ...
}
```

### 3. Thread/Goroutine/Worker Pool Without Shutdown

**Pattern:** Creating workers that outlive their intended scope.

**Java:**
```java
// BAD: Threads prevent clean shutdown
ExecutorService executor = Executors.newFixedThreadPool(10);
// No shutdown hook

// GOOD: Managed lifecycle
@PreDestroy
public void cleanup() {
    executor.shutdown();
    if (!executor.awaitTermination(30, TimeUnit.SECONDS)) {
        executor.shutdownNow();
    }
}
```

**Python:**
```python
# BAD: Threads never joined
def process():
    for item in items:
        t = threading.Thread(target=work, args=(item,))
        t.start()
        # threads never joined

# GOOD: Managed pool
with ThreadPoolExecutor(max_workers=10) as executor:
    executor.map(work, items)
```

**Go:**
```go
// BAD: Goroutine leak
func process(ch chan int) {
    for item := range items {
        go func(i int) {
            result <- expensiveWork(i)  // If result channel full, blocked forever
        }(item)
    }
}

// GOOD: Bounded workers
func process(items []int, workers int) {
    sem := make(chan struct{}, workers)
    var wg sync.WaitGroup
    for _, item := range items {
        wg.Add(1)
        sem <- struct{}{}
        go func(i int) {
            defer wg.Done()
            defer func() { <-sem }()
            expensiveWork(i)
        }(item)
    }
    wg.Wait()
}
```

### 4. Unbounded Cache/Map of Resources

**Pattern:** Caching objects that hold resources without eviction.

```java
// BAD: Unbounded, each entry holds connection
Map<String, Session> sessions = new ConcurrentHashMap<>();
public Session getSession(String id) {
    return sessions.computeIfAbsent(id, Session::new);
}

// GOOD: Bounded with cleanup
LoadingCache<String, Session> sessions = CacheBuilder.newBuilder()
    .maximumSize(1000)
    .expireAfterAccess(1, TimeUnit.HOURS)
    .removalListener(n -> n.getValue().close())
    .build(Session::new);
```

```python
# BAD: Dict grows forever
connections = {}
def get_connection(host):
    if host not in connections:
        connections[host] = create_connection(host)
    return connections[host]

# GOOD: LRU with cleanup
from functools import lru_cache
@lru_cache(maxsize=100)
def get_connection(host):
    return create_connection(host)
# Or use cachetools with TTL
```

### 5. Event Listener / Callback Without Deregistration

**Pattern:** Registering handlers that hold strong references.

```java
// BAD: 'this' can never be GC'd
eventBus.register(this::onEvent);

// GOOD: Explicit lifecycle
private Subscription subscription;
public void start() {
    subscription = eventBus.subscribe(this::onEvent);
}
public void stop() {
    subscription.unsubscribe();
}
```

```javascript
// BAD: Listener keeps component alive
window.addEventListener('resize', this.handleResize);

// GOOD: Cleanup on unmount
componentDidMount() {
    window.addEventListener('resize', this.handleResize);
}
componentWillUnmount() {
    window.removeEventListener('resize', this.handleResize);
}
```

## Code Review Checklist

For every PR that touches I/O, networking, or external services:

### Language-Agnostic Red Flags

| Pattern | Question to Ask |
|---------|-----------------|
| `new XxxClient(` / `XxxClient()` | Should this be a singleton/pooled? |
| `new XxxConnection(` / `connect()` | Is cleanup guaranteed (try-with/context manager/defer)? |
| `new Thread(` / `threading.Thread(` / `go func()` | Who manages lifecycle? |
| `Executors.new` / `ThreadPoolExecutor(` | Where is shutdown called? |
| `.register(` / `.subscribe(` / `.addEventListener(` | Where is deregistration? |
| `Map<>` / `dict` / `map[]` field holding resources | Can it grow unbounded? |
| Object created in loop/handler | Is it reused across calls? |
| `open(` / `fopen(` / `File.Open(` | Is it inside with/using/try-with/defer? |

### Language-Specific Patterns

**Java:**
- `implements AutoCloseable` but no try-with-resources
- `@Inject` missing on client field (means manual instantiation)
- `static` mutable fields holding connections

**Python:**
- Missing `with` for file/connection operations
- `__del__` relying on GC for cleanup (unreliable)
- `atexit.register` without corresponding cleanup

**Go:**
- Missing `defer resp.Body.Close()`
- Goroutine without termination signal (context/channel)
- `sync.Pool` with resources that need explicit close

**JavaScript/TypeScript:**
- Missing cleanup in `useEffect` return / `componentWillUnmount`
- Event listeners without `removeEventListener`
- Intervals/timeouts without `clearInterval`/`clearTimeout`

**C#:**
- `IDisposable` without `using` statement
- Missing `Dispose()` in finalizer pattern

### Green Patterns (Usually Safe)

| Pattern | Why It's Safe |
|---------|---------------|
| `@Singleton` / `@ApplicationScoped` / singleton pattern | Framework manages lifecycle |
| `with` / `using` / `try-with-resources` / `defer` | Guaranteed cleanup |
| `@Inject` / `@Autowired` / DI container | Framework manages lifecycle |
| Connection pool / client pool | Pool manages lifecycle |
| `WeakReference` / `weak_ref` | GC can collect |

## Why Tests Don't Catch These

| Test Type | Why It Misses Leaks |
|-----------|---------------------|
| **Unit tests** | Mock dependencies → no real resources created |
| **Integration tests** | Process exits after tests → OS reclaims everything |
| **Single-request tests** | 1 leaked resource is invisible |
| **CI pipeline** | Fresh process per build → no accumulation |
| **Load tests (short)** | 5 minutes isn't enough to exhaust pools |

**Production is different:**
- Process runs for hours/days/weeks
- Every request leaks a little more
- Eventually: OOM, file descriptor exhaustion, thread exhaustion, connection pool exhaustion

## Detection Strategies

### 1. Resource Count Assertions

**Java:**
```java
@Test
public void noResourceLeak() {
    int threadsBefore = Thread.activeCount();
    int fdBefore = getOpenFileDescriptorCount();
    
    for (int i = 0; i < 100; i++) {
        service.handleRequest();
    }
    
    System.gc(); Thread.sleep(1000);  // Allow cleanup
    
    int threadsAfter = Thread.activeCount();
    int fdAfter = getOpenFileDescriptorCount();
    
    assertTrue("Thread leak", threadsAfter - threadsBefore < 5);
    assertTrue("FD leak", fdAfter - fdBefore < 5);
}

private long getOpenFileDescriptorCount() {
    return ((UnixOperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean())
        .getOpenFileDescriptorCount();
}
```

**Python:**
```python
import resource
import threading

def test_no_resource_leak():
    threads_before = threading.active_count()
    fd_before = len(os.listdir('/proc/self/fd'))  # Linux
    
    for _ in range(100):
        service.handle_request()
    
    gc.collect()
    time.sleep(1)
    
    threads_after = threading.active_count()
    fd_after = len(os.listdir('/proc/self/fd'))
    
    assert threads_after - threads_before < 5, "Thread leak"
    assert fd_after - fd_before < 5, "FD leak"
```

**Go:**
```go
func TestNoLeak(t *testing.T) {
    before := runtime.NumGoroutine()
    
    for i := 0; i < 100; i++ {
        handleRequest()
    }
    
    runtime.GC()
    time.Sleep(time.Second)
    
    after := runtime.NumGoroutine()
    if after-before > 5 {
        t.Errorf("Goroutine leak: %d → %d", before, after)
    }
}
```

### 2. Soak Test Pattern

Run many iterations and check resources stay bounded:

```bash
# Monitor during load test
while true; do
    echo "$(date): threads=$(ps -o nlwp= -p $PID) fds=$(ls /proc/$PID/fd | wc -l)"
    sleep 10
done
```

### 3. Production Monitoring Alerts

```yaml
# Prometheus alert example
- alert: ThreadCountGrowing
  expr: increase(jvm_threads_live_threads[1h]) > 100
  labels:
    severity: warning
  annotations:
    summary: "Thread count growing steadily - possible leak"

- alert: FileDescriptorExhaustion  
  expr: process_open_fds / process_max_fds > 0.8
  labels:
    severity: critical
```

## Verification After Fix

1. **Before/after resource count:** Should be stable across many calls
2. **Heap dump / goroutine dump:** No growing collection of client objects
3. **Connection pool metrics:** Active connections return to baseline
4. **Soak test:** 10x normal load for 1 hour, verify metrics stable

## Common Fixes

| Problem | Fix |
|---------|-----|
| Per-request client | Move to singleton / inject via DI |
| Missing cleanup | Add try-with-resources / context manager / defer |
| Unbounded cache | Add max size + eviction + cleanup callback |
| No shutdown hook | Add @PreDestroy / atexit / signal handler |
| Listener not removed | Store reference, remove in cleanup method |

## Process

1. **Identify the leak type** using the five patterns above
2. **Find all instances** via grep/search for the anti-pattern
3. **Apply the standard fix** from the table above
4. **Add a resource-count test** to prevent regression
5. **Add monitoring** for the resource type in production
