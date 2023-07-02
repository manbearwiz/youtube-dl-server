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
  $cookies.set(key, value, -1, '/', '', true, 'Strict');
}

function getConfig(key, defaultValue) {
  return $cookies.get(key) || defaultValue;
}


export { getAPIUrl, saveConfig, getConfig };
