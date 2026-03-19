"""
Performance testing utilities for Connectly API
Run this in Django shell to test performance improvements
"""

import time
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
import json

class PerformanceTest:
    """Simple performance testing utilities"""
    
    def __init__(self):
        self.client = Client()
        self.results = {}
    
    def measure_response_time(self, func, *args, **kwargs):
        """Measure execution time of a function in seconds"""
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        return result, end - start
    
    def test_feed_performance(self, url, iterations=5, auth_token=None):
        """
        Test feed endpoint performance
        Returns average response time and individual times
        """
        print(f"\n{'='*60}")
        print(f"TESTING FEED PERFORMANCE: {url}")
        print(f"{'='*60}")
        
        times = []
        headers = {}
        if auth_token:
            headers['HTTP_AUTHORIZATION'] = f'Token {auth_token}'
        
        for i in range(iterations):
            start = time.time()
            if auth_token:
                response = self.client.get(url, **headers)
            else:
                response = self.client.get(url)
            end = time.time()
            
            response_time = end - start
            times.append(response_time)
            
            status = "✓" if response.status_code == 200 else "✗"
            print(f"Request {i+1}: {response_time:.4f}s {status}")
        
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"\n📊 RESULTS:")
        print(f"   Average: {avg_time:.4f}s")
        print(f"   Min: {min_time:.4f}s")
        print(f"   Max: {max_time:.4f}s")
        print(f"   Improvement: {(times[0] - avg_time) / times[0] * 100:.1f}% (first vs avg)")
        
        self.results['feed'] = {
            'avg': avg_time,
            'min': min_time,
            'max': max_time,
            'times': times
        }
        
        return times
    
    def test_cache_effectiveness(self, url, iterations=10, auth_token=None):
        """
        Test cache hit rate and effectiveness
        """
        print(f"\n{'='*60}")
        print(f"TESTING CACHE EFFECTIVENESS: {url}")
        print(f"{'='*60}")
        
        times = []
        hits = 0
        headers = {}
        if auth_token:
            headers['HTTP_AUTHORIZATION'] = f'Token {auth_token}'
        
        for i in range(iterations):
            start = time.time()
            if auth_token:
                response = self.client.get(url, **headers)
            else:
                response = self.client.get(url)
            end = time.time()
            
            response_time = end - start
            times.append(response_time)
            
            # Check if response has cached flag (if you added it)
            try:
                data = json.loads(response.content)
                is_cached = data.get('cached', False)
                if is_cached:
                    hits += 1
                    cache_status = "HIT  ✓"
                else:
                    cache_status = "MISS ✗"
            except:
                cache_status = "unknown"
            
            print(f"Request {i+1}: {response_time:.4f}s [{cache_status}]")
        
        hit_rate = (hits / iterations) * 100 if iterations > 0 else 0
        
        print(f"\n📊 CACHE RESULTS:")
        print(f"   Cache Hits: {hits}/{iterations}")
        print(f"   Hit Rate: {hit_rate:.1f}%")
        print(f"   Avg Response: {sum(times)/len(times):.4f}s")
        
        self.results['cache'] = {
            'hits': hits,
            'total': iterations,
            'hit_rate': hit_rate,
            'avg_time': sum(times)/len(times)
        }
        
        return hit_rate
    
    def compare_without_cache(self, url, auth_token=None):
        """
        Compare performance with and without cache
        """
        print(f"\n{'='*60}")
        print(f"COMPARING WITH VS WITHOUT CACHE")
        print(f"{'='*60}")
        
        # First request (cache miss)
        start = time.time()
        headers = {}
        if auth_token:
            headers['HTTP_AUTHORIZATION'] = f'Token {auth_token}'
            response = self.client.get(url, **headers)
        else:
            response = self.client.get(url)
        first_time = time.time() - start
        
        # Second request (potential cache hit)
        start = time.time()
        if auth_token:
            response = self.client.get(url, **headers)
        else:
            response = self.client.get(url)
        second_time = time.time() - start
        
        print(f"First request (cache miss):  {first_time:.4f}s")
        print(f"Second request (cache hit): {second_time:.4f}s")
        print(f"Speed improvement: {(first_time - second_time) / first_time * 100:.1f}% faster")
        
        return first_time, second_time
    
    def test_post_detail_performance(self, post_id, auth_token=None):
        """
        Test post detail endpoint performance
        """
        url = f'/posts/post/{post_id}/'
        return self.test_cache_effectiveness(url, iterations=5, auth_token=auth_token)
    
    def print_summary(self):
        """Print summary of all tests"""
        print(f"\n{'='*60}")
        print(f"📋 PERFORMANCE TEST SUMMARY")
        print(f"{'='*60}")
        
        if 'feed' in self.results:
            f = self.results['feed']
            print(f"Feed: avg {f['avg']:.3f}s | min {f['min']:.3f}s | max {f['max']:.3f}s")
        
        if 'cache' in self.results:
            c = self.results['cache']
            print(f"Cache: {c['hit_rate']:.1f}% hit rate | avg {c['avg_time']:.3f}s")
        
        print(f"{'='*60}\n")


# Quick test function to run from shell
def run_performance_tests(token=None):
    """
    Run all performance tests
    Usage:
        from posts.performance import run_performance_tests
        run_performance_tests('your_auth_token')
    """
    tester = PerformanceTest()
    
    # Test feed
    tester.test_feed_performance('/posts/feed/?page=1&page_size=5', auth_token=token)
    
    # Test cache effectiveness
    tester.test_cache_effectiveness('/posts/feed/?page=1&page_size=5', auth_token=token)
    
    # Test post detail (use a real post ID from your database)
    tester.test_post_detail_performance(post_id=1, auth_token=token)
    
    # Comparison
    tester.compare_without_cache('/posts/feed/?page=1&page_size=5', auth_token=token)
    
    tester.print_summary()
    
    return tester.results