package watcher

import (
	"context"
	"log"
	"sync"
	"time"

	"sam-client/pkg/collector"
	"sam-client/pkg/model"
)

// ProcessEventCallback функция обратного вызова при обнаружении нового процесса
type ProcessEventCallback func(proc model.ProcessItem)

// RegistryEventCallback функция обратного вызова при изменении реестра установленного ПО
type RegistryEventCallback func()

// WatcherManager координирует наблюдение за процессами и реестром в реальном времени
type WatcherManager struct {
	onProcessStart  ProcessEventCallback
	onRegistryDelta RegistryEventCallback

	knownPIDs   map[uint32]string
	knownPIDsMu sync.RWMutex

	pollInterval time.Duration
	cancelFunc   context.CancelFunc
	wg           sync.WaitGroup
}

// NewWatcherManager создает менеджер наблюдателей
func NewWatcherManager(onProc ProcessEventCallback, onReg RegistryEventCallback) *WatcherManager {
	return &WatcherManager{
		onProcessStart:  onProc,
		onRegistryDelta: onReg,
		knownPIDs:       make(map[uint32]string),
		pollInterval:    3 * time.Second,
	}
}

// Start запускает фоновый мониторинг
func (wm *WatcherManager) Start(ctx context.Context) {
	watcherCtx, cancel := context.WithCancel(ctx)
	wm.cancelFunc = cancel

	// 1. Инициализация снимка процессов
	initialProcs, err := collector.Collect(collector.Options{IncludeStandalone: false, Thorough: false})
	if err == nil {
		wm.knownPIDsMu.Lock()
		for _, p := range initialProcs.RunningProcesses {
			wm.knownPIDs[p.PID] = p.Name
		}
		wm.knownPIDsMu.Unlock()
	}

	// 2. Фоновый мониторинг запущенных процессов
	wm.wg.Add(1)
	go wm.runProcessWatcher(watcherCtx)

	// 3. Фоновый мониторинг изменений в системном реестре ПО
	wm.wg.Add(1)
	go wm.runRegistryWatcher(watcherCtx)
}

// Stop останавливает мониторинг
func (wm *WatcherManager) Stop() {
	if wm.cancelFunc != nil {
		wm.cancelFunc()
	}
	wm.wg.Wait()
}

func (wm *WatcherManager) runProcessWatcher(ctx context.Context) {
	defer wm.wg.Done()
	ticker := time.NewTicker(wm.pollInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			wm.checkProcessesDelta()
		}
	}
}

func (wm *WatcherManager) checkProcessesDelta() {
	currentReport, err := collector.Collect(collector.Options{IncludeStandalone: false, Thorough: false})
	if err != nil {
		return
	}

	currentPIDs := make(map[uint32]string)
	for _, p := range currentReport.RunningProcesses {
		currentPIDs[p.PID] = p.Name
	}

	wm.knownPIDsMu.Lock()
	var newProcs []model.ProcessItem
	for _, p := range currentReport.RunningProcesses {
		if _, existed := wm.knownPIDs[p.PID]; !existed {
			newProcs = append(newProcs, p)
		}
	}
	wm.knownPIDs = currentPIDs
	wm.knownPIDsMu.Unlock()

	for _, p := range newProcs {
		if p.ExePath != "" {
			collector.RecordProcessExecution(p.ExePath, time.Now().UTC())
		}
		if wm.onProcessStart != nil {
			wm.onProcessStart(p)
		}
	}
}

func (wm *WatcherManager) runRegistryWatcher(ctx context.Context) {
	defer wm.wg.Done()
	// Запуск платформенно-специфичного вотчера реестра
	startPlatformRegistryWatcher(ctx, func() {
		log.Printf("[*] [Watcher] Обнаружено изменение в реестре установленного ПО!")
		if wm.onRegistryDelta != nil {
			wm.onRegistryDelta()
		}
	})
}
