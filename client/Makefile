GOCMD ?= /usr/local/go/bin/go
BIN_DIR = bin
APP_NAME = sam-agent

.PHONY: all build build-windows build-linux test clean

all: build

build: build-windows

build-windows:
	@mkdir -p $(BIN_DIR)
	@echo "Building Windows amd64 binary..."
	GOOS=windows GOARCH=amd64 $(GOCMD) build -trimpath -ldflags="-s -w" -o $(BIN_DIR)/$(APP_NAME).exe ./cmd/sam-agent
	@echo "Windows binary created: $(BIN_DIR)/$(APP_NAME).exe"

build-linux:
	@mkdir -p $(BIN_DIR)
	@echo "Building Linux binary for local dev/testing..."
	$(GOCMD) build -trimpath -o $(BIN_DIR)/$(APP_NAME) ./cmd/sam-agent
	@echo "Linux binary created: $(BIN_DIR)/$(APP_NAME)"

test:
	$(GOCMD) test -v ./...

clean:
	rm -rf $(BIN_DIR)
	rm -f *.csv *.json
