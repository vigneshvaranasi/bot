import { BE_URL } from '../config/config';

const getHeaders = () => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const token = localStorage.getItem('token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

const handleResponse = async (response: Response) => {
  if (response.status === 401) {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    if (!window.location.pathname.startsWith('/auth')) {
      window.location.href = '/auth';
    }
    return Promise.reject(new Error('Unauthorized'));
  }
  
  const data = await response.json().catch(() => null);
  
  if (!response.ok) {
    const error = new Error(data?.detail || response.statusText || 'Request failed');
    (error as any).response = { status: response.status, data };
    return Promise.reject(error);
  }
  
  return { data };
};

const http = {
  get: async (url: string) => {
    const response = await fetch(`${BE_URL}${url}`, {
      method: 'GET',
      headers: getHeaders(),
    });
    return handleResponse(response);
  },
  post: async (url: string, body?: any) => {
    const response = await fetch(`${BE_URL}${url}`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(body),
    });
    return handleResponse(response);
  },
  put: async (url: string, body?: any) => {
    const response = await fetch(`${BE_URL}${url}`, {
      method: 'PUT',
      headers: getHeaders(),
      body: JSON.stringify(body),
    });
    return handleResponse(response);
  },
  delete: async (url: string) => {
    const response = await fetch(`${BE_URL}${url}`, {
      method: 'DELETE',
      headers: getHeaders(),
    });
    return handleResponse(response);
  },
};

export default http;
