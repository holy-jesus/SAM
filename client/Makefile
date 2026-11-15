GOCMD ?= go
BIN_DIR = bin
APP_NAME = sam-agent
GUI_NAME = sam-gui

.PHONY: all build build-windows build-linux test installer clean

all: build

build: build-windows build-linux

build-windows:
	@mkdir -p $(BIN_DIR)
	@echo "Building Windows amd64 binaries (Agent & GUI)..."
	GOOS=windows GOARCH=amd64 $(GOCMD) build -trimpath -ldflags="-s -w" -o $(BIN_DIR)/$(APP_NAME).exe ./cmd/sam-agent
	GOOS=windows GOARCH=amd64 $(GOCMD) build -trimpath -ldflags="-s -w" -o $(BIN_DIR)/$(GUI_NAME).exe ./cmd/sam-gui
	@echo "Windows binaries created in $(BIN_DIR)/: $(APP_NAME).exe, $(GUI_NAME).exe"

build-linux:
	@mkdir -p $(BIN_DIR)
	@echo "Building Linux binaries for local dev/testing (Agent & GUI)..."
	$(GOCMD) build -trimpath -o $(BIN_DIR)/$(APP_NAME) ./cmd/sam-agent
	$(GOCMD) build -trimpath -o $(BIN_DIR)/$(GUI_NAME) ./cmd/sam-gui
	@echo "Linux binaries created in $(BIN_DIR)/: $(APP_NAME), $(GUI_NAME)"

installer: build-windows
	@if command -v makensis >/dev/null 2>&1; then \
		echo "Building NSIS Installer for Windows..."; \
		makensis installer/installer.nsi; \
		echo "Installer generated successfully in $(BIN_DIR)/"; \
	else \
		echo "makensis is not installed. To build installer on Linux: sudo apt-get install nsis, or run NSIS on Windows."; \
	fi

test:
	$(GOCMD) test -v ./...

clean:
	rm -rf $(BIN_DIR)
	rm -f *.csv *.json
