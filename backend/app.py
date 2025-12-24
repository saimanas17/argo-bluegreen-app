from flask import Flask, jsonify
from flask_cors import CORS
from kubernetes import client, config
import os
import socket
import redis
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Try to load in-cluster config, fall back to kubeconfig for local development
try:
    config.load_incluster_config()
    print("Loaded in-cluster Kubernetes config")
except:
    try:
        config.load_kube_config()
        print("Loaded kubeconfig for local development")
    except:
        print("Could not load Kubernetes config - running in demo mode")

# Get environment variables
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')
BUILD_NUMBER = os.getenv('BUILD_NUMBER', 'local')
DEPLOYMENT_COLOR = os.getenv('DEPLOYMENT_COLOR', 'blue')
NAMESPACE = os.getenv('NAMESPACE', 'default')

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

# Initialize Redis connection
redis_client = None
redis_connected = False

try:
    if REDIS_PASSWORD:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5
        )
    else:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=5
        )
    
    # Test connection
    redis_client.ping()
    redis_connected = True
    print(f"✓ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    print(f"✗ Redis connection failed: {str(e)}")
    redis_connected = False

@app.route('/api/health', methods=['GET'])
def health():
    """Basic health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'backend',
        'redis': 'connected' if redis_connected else 'disconnected'
    }), 200

@app.route('/api/version', methods=['GET'])
def get_version():
    """Get version information"""
    hostname = socket.gethostname()
    
    return jsonify({
        'hostname': hostname,
        'buildNumber': BUILD_NUMBER,
        'environment': ENVIRONMENT,
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/api/info', methods=['GET'])
def get_info():
    """Get deployment information"""
    hostname = socket.gethostname()
    
    # Get Redis info
    redis_info = {
        'connected': redis_connected,
        'host': REDIS_HOST,
        'port': REDIS_PORT,
        'passwordConfigured': bool(REDIS_PASSWORD)
    }
    
    if redis_connected:
        try:
            redis_server_info = redis_client.info('server')
            redis_info['version'] = redis_server_info.get('redis_version', 'unknown')
            redis_info['uptime_days'] = redis_server_info.get('uptime_in_days', 0)
        except:
            pass
    
    # Increment page view counter
    if redis_connected:
        try:
            redis_client.incr('total_views')
            redis_client.incr(f'backend_views:{hostname}')
        except Exception as e:
            print(f"Error incrementing counter: {e}")
    
    return jsonify({
        'environment': ENVIRONMENT,
        'buildNumber': BUILD_NUMBER,
        'deploymentColor': DEPLOYMENT_COLOR,
        'hostname': hostname,
        'namespace': NAMESPACE,
        'redis': redis_info
    }), 200

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get view statistics from Redis"""
    if not redis_connected:
        return jsonify({
            'error': 'Redis not connected',
            'total_views': 0,
            'backend_views': {}
        }), 200
    
    try:
        total_views = redis_client.get('total_views') or '0'
        
        # Get all backend pod view counts
        backend_keys = redis_client.keys('backend_views:*')
        backend_views = {}
        for key in backend_keys:
            pod_name = key.replace('backend_views:', '')
            backend_views[pod_name] = redis_client.get(key)
        
        return jsonify({
            'total_views': int(total_views),
            'backend_views': backend_views,
            'last_updated': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'error': str(e),
            'total_views': 0,
            'backend_views': {}
        }), 500

@app.route('/api/pods', methods=['GET'])
def get_pods():
    """Get pod information from Kubernetes"""
    try:
        v1 = client.CoreV1Api()
        
        # Get all frontend pods with rollout info
        pods = v1.list_namespaced_pod(
            namespace=NAMESPACE,
            label_selector='app=nginx-bluegreen'
        )
        
        pod_info = []
        
        # Get active and preview service selectors
        active_hash = None
        preview_hash = None
        
        try:
            active_svc = v1.read_namespaced_service('frontend-service-active', NAMESPACE)
            preview_svc = v1.read_namespaced_service('frontend-service-preview', NAMESPACE)
            
            active_hash = active_svc.spec.selector.get('rollouts-pod-template-hash')
            preview_hash = preview_svc.spec.selector.get('rollouts-pod-template-hash')
            
            print(f"Active hash from service: {active_hash}")
            print(f"Preview hash from service: {preview_hash}")
        except Exception as e:
            print(f"Error getting service selectors: {e}")
        
        for pod in pods.items:
            pod_hash = pod.metadata.labels.get('rollouts-pod-template-hash', 'unknown')
            
            # Determine if pod is active or preview based on hash
            version = 'unknown'
            if active_hash and pod_hash == active_hash:
                version = 'active'
            elif preview_hash and pod_hash == preview_hash:
                version = 'preview'
            elif active_hash is None and preview_hash is None:
                # If services don't have hashes, mark all as unknown
                version = 'unknown'
            
            # Get pod status
            phase = pod.status.phase
            ready = False
            
            if pod.status.container_statuses:
                ready = all(cs.ready for cs in pod.status.container_statuses)
            
            pod_info.append({
                'name': pod.metadata.name,
                'version': version,
                'status': phase,
                'ready': ready,
                'ip': pod.status.pod_ip,
                'node': pod.spec.node_name,
                'restarts': sum(cs.restart_count for cs in pod.status.container_statuses) if pod.status.container_statuses else 0,
                'hash': pod_hash
            })
        
        # Count by version
        active_count = sum(1 for p in pod_info if p['version'] == 'active')
        preview_count = sum(1 for p in pod_info if p['version'] == 'preview')
        unknown_count = sum(1 for p in pod_info if p['version'] == 'unknown')
        
        return jsonify({
            'pods': pod_info,
            'summary': {
                'total': len(pod_info),
                'active': active_count,
                'preview': preview_count,
                'unknown': unknown_count
            },
            'debug': {
                'active_hash': active_hash,
                'preview_hash': preview_hash
            }
        }), 200
        
    except Exception as e:
        print(f"Error getting pods: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'pods': [],
            'summary': {
                'total': 0,
                'active': 0,
                'preview': 0,
                'unknown': 0
            },
            'error': str(e)
        }), 200

@app.route('/api/service', methods=['GET'])
def get_service():
    """Get current service routing information"""
    try:
        v1 = client.CoreV1Api()
        
        # Get both active and preview services
        active_svc = v1.read_namespaced_service('frontend-service-active', NAMESPACE)
        preview_svc = v1.read_namespaced_service('frontend-service-preview', NAMESPACE)
        
        active_selector = active_svc.spec.selector
        preview_selector = preview_svc.spec.selector
        
        active_hash = active_selector.get('rollouts-pod-template-hash', 'none')
        preview_hash = preview_selector.get('rollouts-pod-template-hash', 'none')
        
        return jsonify({
            'activeService': {
                'name': 'frontend-service-active',
                'selector': active_selector,
                'hash': active_hash,
                'clusterIP': active_svc.spec.cluster_ip,
                'nodePort': 30080
            },
            'previewService': {
                'name': 'frontend-service-preview',
                'selector': preview_selector,
                'hash': preview_hash,
                'clusterIP': preview_svc.spec.cluster_ip,
                'nodePort': 30081
            }
        }), 200
        
    except Exception as e:
        print(f"Error getting service: {str(e)}")
        return jsonify({
            'activeService': {
                'name': 'frontend-service-active',
                'nodePort': 30080
            },
            'previewService': {
                'name': 'frontend-service-preview',
                'nodePort': 30081
            },
            'note': 'Error getting services'
        }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)