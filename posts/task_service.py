import requests

TASK_API_URL = "http://127.0.0.1:8001/tasks/"

def get_user_tasks(user_id):
    try:
        response = requests.get(f"{TASK_API_URL}?assigned_to={user_id}")
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def get_one_task(task_id):
    try:
        response = requests.get(f"{TASK_API_URL}{task_id}/")
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def create_task_in_api(title, description, assigned_to):
    try:
        data = {
            'title': title,
            'description': description,
            'assigned_to': assigned_to,
            'status': 'pending'
        }
        response = requests.post(TASK_API_URL, json=data)
        print(f"Task API response: {response.status_code}")  # This will show in terminal
        if response.status_code == 201:
            return response.json()
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None