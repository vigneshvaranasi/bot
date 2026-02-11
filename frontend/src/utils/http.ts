import { BE_URL } from '../config/config';

interface HttpError extends Error {
  response?: { status: number; data: unknown };
}

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
    const error: HttpError = new Error(data?.detail || response.statusText || 'Request failed');
    error.response = { status: response.status, data };
    return Promise.reject(error);
  }

  return { data };
};

const http = {
  get: async <T = any>(url: string): Promise<{ data: T }> => {
    const response = await fetch(`${BE_URL}${url}`, {
      method: 'GET',
      headers: getHeaders(),
    });
    return handleResponse(response) as Promise<{ data: T }>;
  },
  post: async <T = any>(url: string, body?: unknown): Promise<{ data: T }> => {
    const response = await fetch(`${BE_URL}${url}`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(body),
    });
    return handleResponse(response) as Promise<{ data: T }>;
  },
  put: async <T = any>(url: string, body?: unknown): Promise<{ data: T }> => {
    const response = await fetch(`${BE_URL}${url}`, {
      method: 'PUT',
      headers: getHeaders(),
      body: JSON.stringify(body),
    });
    return handleResponse(response) as Promise<{ data: T }>;
  },
  delete: async (url: string): Promise<{ data: any }> => {
    const response = await fetch(`${BE_URL}${url}`, {
      method: 'DELETE',
      headers: getHeaders(),
    });
    return handleResponse(response) as Promise<{ data: any }>;
  },
};

export default http;
