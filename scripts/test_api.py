# Test API endpoints for Pet Translator
# Usage: python test_api.py

import requests
import json
import base64

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("\n[TEST] Health Check")
    resp = requests.get(f"{BASE_URL}/health")
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
    return resp.status_code == 200

def test_fusion_analyze():
    """Test fusion analysis with sample data"""
    print("\n[TEST] Fusion Analysis")
    data = {
        "pet_id": "pet_001",
        "audio": {
            "animal": "狗",
            "behavior": "吠叫",
            "confidence": 0.95,
            "is_pet_sound": True,
            "is_alert": True,
            "suggestion": "检查是否有陌生人"
        },
        "visual": {
            "behavior": "站立",
            "confidence": 0.8,
            "activity_level": "high",
            "is_destructive": False,
            "description": "狗在门口站立",
            "detections": []
        }
    }
    resp = requests.post(f"{BASE_URL}/api/fusion/analyze", json=data)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
    return resp.status_code == 200

def test_pets():
    """Test pets endpoints"""
    print("\n[TEST] Pets List")
    resp = requests.get(f"{BASE_URL}/api/pets")
    print(f"  Status: {resp.status_code}")
    print(f"  Pets: {len(resp.json())} found")
    return resp.status_code == 200

def test_daily_report():
    """Test daily report generation"""
    print("\n[TEST] Daily Report")
    resp = requests.get(f"{BASE_URL}/api/report/daily")
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
    return resp.status_code == 200

def test_events():
    """Test events list"""
    print("\n[TEST] Events List")
    resp = requests.get(f"{BASE_URL}/api/events")
    print(f"  Status: {resp.status_code}")
    print(f"  Events: {len(resp.json())} found")
    return resp.status_code == 200

def main():
    print("=" * 50)
    print("Pet Translator API Tests")
    print("=" * 50)
    
    tests = [
        ("Health Check", test_health),
        ("Pets List", test_pets),
        ("Fusion Analyze", test_fusion_analyze),
        ("Daily Report", test_daily_report),
        ("Events List", test_events),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            print(f"  Result: {'PASS' if result else 'FAIL'}")
        except Exception as e:
            print(f"  Error: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    passed = sum(1 for _, r in results if r)
    print(f"Passed: {passed}/{len(results)}")
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")

if __name__ == "__main__":
    main()
