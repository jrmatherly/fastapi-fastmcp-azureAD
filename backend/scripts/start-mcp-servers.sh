#!/bin/bash
set -e

echo "🚀 Starting MCP Servers..."

# Configuration
BACKEND_DIR="/app"
LOG_DIR="/app/logs/mcp"
mkdir -p "$LOG_DIR"

# Function to start an MCP server
start_mcp_server() {
    local server_name="$1"
    local module="$2"
    local port="$3"

    echo "📡 Starting $server_name on port $port..."

    # Start server in background
    uvicorn "$module" \
        --host 0.0.0.0 \
        --port "$port" \
        --reload \
        --access-log \
        --log-config /dev/null \
        > "$LOG_DIR/$server_name.log" 2>&1 &

    local pid=$!
    echo "$pid" > "$LOG_DIR/$server_name.pid"

    echo "✅ Started $server_name (PID: $pid, Port: $port)"

    # Wait a moment and check if it's still running
    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        echo "✅ $server_name is healthy"
    else
        echo "❌ $server_name failed to start"
        return 1
    fi
}

# Function to stop all MCP servers
stop_mcp_servers() {
    echo "🔄 Stopping MCP servers..."

    for pidfile in "$LOG_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            local pid=$(cat "$pidfile")
            local server_name=$(basename "$pidfile" .pid)

            if kill -0 "$pid" 2>/dev/null; then
                echo "🛑 Stopping $server_name (PID: $pid)..."
                kill -TERM "$pid"

                # Wait for graceful shutdown
                for i in {1..10}; do
                    if ! kill -0 "$pid" 2>/dev/null; then
                        break
                    fi
                    sleep 1
                done

                # Force kill if still running
                if kill -0 "$pid" 2>/dev/null; then
                    echo "⚡ Force killing $server_name..."
                    kill -KILL "$pid"
                fi

                echo "✅ Stopped $server_name"
            fi

            rm -f "$pidfile"
        fi
    done
}

# Trap signals for graceful shutdown
trap stop_mcp_servers EXIT TERM INT

# Start MCP servers
start_mcp_server "weather" "app.mcp.weather_server:app" "8001"
# start_mcp_server "finance" "app.mcp.finance_server:app" "8002"  # Future servers

echo "🎉 All MCP servers started successfully!"
echo "📋 Server status:"
echo "  - Weather MCP: http://localhost:8001"
echo "  - Logs: $LOG_DIR/"

# Keep script running to maintain processes
while true; do
    sleep 30

    # Health check - restart any dead servers
    for pidfile in "$LOG_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            local pid=$(cat "$pidfile")
            local server_name=$(basename "$pidfile" .pid)

            if ! kill -0 "$pid" 2>/dev/null; then
                echo "⚠️  $server_name died, restarting..."
                case "$server_name" in
                    "weather")
                        start_mcp_server "weather" "app.mcp.weather_server:app" "8001"
                        ;;
                    # Add other servers here
                esac
            fi
        fi
    done
done
