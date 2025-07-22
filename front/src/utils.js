import { get } from 'lodash';

function getAPIUrl(path, env) {
  const VITE_YOUTUBE_DL_SERVER_API_URL = get(env, 'VITE_YOUTUBE_DL_SERVER_API_URL', '');
  if (VITE_YOUTUBE_DL_SERVER_API_URL) {
    if (VITE_YOUTUBE_DL_SERVER_API_URL.endsWith('/')) {
      return `${VITE_YOUTUBE_DL_SERVER_API_URL}${path}`;
    }
    return `${VITE_YOUTUBE_DL_SERVER_API_URL}/${path}`;
  }
  return path;
}

function saveConfig(key, value) {
  localStorage.setItem(key, value);
}

function getConfig(key, defaultValue) {
  return localStorage.getItem(key) || defaultValue;
}


export { getAPIUrl, saveConfig, getConfig };
