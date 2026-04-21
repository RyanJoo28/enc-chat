const buildPreviewStorageKey = (userId, scopeKey = 'default') => `e2ee_private_previews:${userId}:${scopeKey}`;
const buildGroupPreviewStorageKey = (userId, scopeKey = 'default') => `e2ee_group_previews:${userId}:${scopeKey}`;

const loadPreviewMap = (userId, scopeKey = 'default') => {
  try {
    const raw = localStorage.getItem(buildPreviewStorageKey(userId, scopeKey));
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (error) {
    console.error(error);
    return {};
  }
};

const savePreviewMap = (userId, scopeKey = 'default', previewMap) => {
  localStorage.setItem(buildPreviewStorageKey(userId, scopeKey), JSON.stringify(previewMap));
};

const loadGroupPreviewMap = (userId, scopeKey = 'default') => {
  try {
    const raw = localStorage.getItem(buildGroupPreviewStorageKey(userId, scopeKey));
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (error) {
    console.error(error);
    return {};
  }
};

const saveGroupPreviewMap = (userId, scopeKey = 'default', previewMap) => {
  localStorage.setItem(buildGroupPreviewStorageKey(userId, scopeKey), JSON.stringify(previewMap));
};

export const getPrivatePreviewEntry = (userId, partnerId, scopeKey = 'default') => {
  return loadPreviewMap(userId, scopeKey)[String(partnerId)] || null;
};

export const savePrivatePreviewEntry = (userId, partnerId, entry, scopeKey = 'default') => {
  const previewMap = loadPreviewMap(userId, scopeKey);
  previewMap[String(partnerId)] = {
    text: entry.text || '',
    timestamp: entry.timestamp || '',
  };
  savePreviewMap(userId, scopeKey, previewMap);
  return previewMap[String(partnerId)];
};

export const buildPrivatePreviewText = (plaintext, isOwnMessage) => {
  const normalized = (plaintext || '').replace(/\s+/g, ' ').trim();
  return isOwnMessage ? `You: ${normalized}` : normalized;
};

export const getPrivatePreviewMap = (userId, scopeKey = 'default') => {
  return loadPreviewMap(userId, scopeKey);
};

export const replacePrivatePreviewMap = (userId, previewMap, scopeKey = 'default') => {
  savePreviewMap(userId, scopeKey, previewMap && typeof previewMap === 'object' ? previewMap : {});
};

export const removePrivatePreviewEntry = (userId, partnerId, scopeKey = 'default') => {
  const previewMap = loadPreviewMap(userId, scopeKey);
  delete previewMap[String(partnerId)];
  savePreviewMap(userId, scopeKey, previewMap);
};

export const getGroupPreviewEntry = (userId, groupId, scopeKey = 'default') => {
  return loadGroupPreviewMap(userId, scopeKey)[String(groupId)] || null;
};

export const saveGroupPreviewEntry = (userId, groupId, entry, scopeKey = 'default') => {
  const previewMap = loadGroupPreviewMap(userId, scopeKey);
  previewMap[String(groupId)] = {
    text: entry.text || '',
    timestamp: entry.timestamp || '',
  };
  saveGroupPreviewMap(userId, scopeKey, previewMap);
  return previewMap[String(groupId)];
};

export const getGroupPreviewMap = (userId, scopeKey = 'default') => {
  return loadGroupPreviewMap(userId, scopeKey);
};

export const replaceGroupPreviewMap = (userId, previewMap, scopeKey = 'default') => {
  saveGroupPreviewMap(userId, scopeKey, previewMap && typeof previewMap === 'object' ? previewMap : {});
};

export const removeGroupPreviewEntry = (userId, groupId, scopeKey = 'default') => {
  const previewMap = loadGroupPreviewMap(userId, scopeKey);
  delete previewMap[String(groupId)];
  saveGroupPreviewMap(userId, scopeKey, previewMap);
};
