#!/bin/bash

echo "========================================="
echo "Radio Transcription System - Test"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check Python
echo -n "Testing Python installation... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}OK${NC} ($PYTHON_VERSION)"
else
    echo -e "${RED}FAILED${NC}"
    echo "  Python 3 is required"
fi

# Test 2: Check HackRF tools
echo -n "Testing HackRF tools... "
if command -v hackrf_info &> /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARNING${NC}"
    echo "  HackRF tools not found - install with: sudo apt-get install hackrf"
fi

# Test 3: Check HackRF device
echo -n "Testing HackRF device connection... "
if hackrf_info &> /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARNING${NC}"
    echo "  HackRF device not detected (will use simulation mode)"
fi

# Test 4: Check Docker
echo -n "Testing Docker installation... "
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo -e "${GREEN}OK${NC} ($DOCKER_VERSION)"
else
    echo -e "${YELLOW}WARNING${NC}"
    echo "  Docker not found - required for Docker deployment"
fi

# Test 5: Check Docker Compose
echo -n "Testing Docker Compose... "
if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || echo "V2")
    echo -e "${GREEN}OK${NC} (V2: $COMPOSE_VERSION)"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version)
    echo -e "${YELLOW}WARNING${NC} (V1: $COMPOSE_VERSION - V2 recommended)"
else
    echo -e "${YELLOW}WARNING${NC}"
    echo "  Docker Compose not found - required for Docker deployment"
fi

# Test 6: Check Python dependencies
echo -n "Testing Python dependencies... "
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    if python -c "import flask, scipy, numpy" 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${YELLOW}WARNING${NC}"
        echo "  Some Python packages missing - run: pip install -r requirements.txt"
    fi
else
    echo -e "${YELLOW}WARNING${NC}"
    echo "  Virtual environment not found - run: ./setup.sh"
fi

# Test 7: Check directories
echo -n "Testing directories... "
if [ -d "recordings" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARNING${NC}"
    echo "  Creating recordings directory..."
    mkdir -p recordings
fi

# Test 8: Test API (if running)
echo -n "Testing API service... "
if curl -s http://localhost:5000/health &> /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}NOT RUNNING${NC}"
    echo "  Start with: ./start.sh or docker compose -f docker-compose.elk.yml up -d"
fi

# Test 9: Test Web Interface (if running)
echo -n "Testing web interface... "
if curl -s http://localhost:8080 &> /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}NOT RUNNING${NC}"
    echo "  Start with: ./start.sh or docker compose -f docker-compose.elk.yml up -d"
fi

# Test 10: Test Kibana (if running)
echo -n "Testing Kibana... "
if curl -s http://localhost:5601 &> /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}NOT RUNNING${NC}"
    echo "  Start with: docker compose -f docker-compose.elk.yml up -d"
fi

echo ""
echo "========================================="
echo "Test Complete!"
echo "========================================="
echo ""
echo "Quick commands:"
echo "  ./setup.sh                                     - Run initial setup"
echo "  ./start.sh                                     - Start services manually"
echo "  docker compose -f docker-compose.elk.yml up -d - Start with Docker (ELK stack)"
echo "  hackrf_info                                    - Check HackRF connection"
echo "  rtl_test -t                                    - Check RTL-SDR connection"
echo ""
