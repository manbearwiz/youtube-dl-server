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

function formatCountdown(timestamp) {
	if (!timestamp) {
		return '';
	}
	const seconds = timestamp - Date.now() / 1000;
	if (seconds <= 0) {
		return 'now';
	}
	if (seconds < 3600) {
		return `in ${Math.ceil(seconds / 60)}m`;
	}
	if (seconds < 86400) {
		return `in ${Math.round(seconds / 3600)}h`;
	}
	return `in ${Math.round(seconds / 86400)}d`;
}

function saveConfig(key, value) {
	localStorage.setItem(key, value);
}

function getConfig(key, defaultValue) {
	return localStorage.getItem(key) || defaultValue;
}


export { getAPIUrl, formatCountdown, saveConfig, getConfig };
