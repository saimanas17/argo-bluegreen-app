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
        
        # Get all pods in the namespace with our app label
        pods = v1.list_namespaced_pod(
            namespace=NAMESPACE,
            label_selector='app=nginx-bluegreen'
        )
        
        pod_info = []
        blue_count = 0
        green_count = 0
        
        for pod in pods.items:
            version = pod.metadata.labels.get('version', 'unknown')
            
            if version == 'blue':
                blue_count += 1
            elif version == 'green':
                green_count += 1
            
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
                'restarts': sum(cs.restart_count for cs in pod.status.container_statuses) if pod.status.container_statuses else 0
            })
        
        return jsonify({
            'pods': pod_info,
            'summary': {
                'total': len(pod_info),
                'blue': blue_count,
                'green': green_count
            }
        }), 200
        
    except Exception as e:
        print(f"Error getting pods: {str(e)}")
        # Return mock data for local development
        return jsonify({
            'pods': [
                {
                    'name': f'nginx-{DEPLOYMENT_COLOR}-demo-1',
                    'version': DEPLOYMENT_COLOR,
                    'status': 'Running',
                    'ready': True,
                    'ip': '10.244.0.1',
                    'node': 'node-1',
                    'restarts': 0
                }
            ],
            'summary': {
                'total': 1,
                'blue': 1 if DEPLOYMENT_COLOR == 'blue' else 0,
                'green': 1 if DEPLOYMENT_COLOR == 'green' else 0
            },
            'note': 'Demo mode - not connected to real cluster'
        }), 200

@app.route('/api/service', methods=['GET'])
def get_service():
    """Get current service routing information"""
    try:
        v1 = client.CoreV1Api()
        
        # Get the service
        service = v1.read_namespaced_service(
            name='nginx-bluegreen',
            namespace=NAMESPACE
        )
        
        # Get the selector to see which version is active
        selector = service.spec.selector
        active_version = selector.get('version', 'unknown')
        
        return jsonify({
            'activeVersion': active_version,
            'selector': selector,
            'clusterIP': service.spec.cluster_ip,
            'ports': [{'port': p.port, 'targetPort': p.target_port} for p in service.spec.ports]
        }), 200
        
    except Exception as e:
        print(f"Error getting service: {str(e)}")
        return jsonify({
            'activeVersion': DEPLOYMENT_COLOR,
            'selector': {'app': 'nginx-bluegreen', 'version': DEPLOYMENT_COLOR},
            'note': 'Demo mode - not connected to real cluster'
        }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
