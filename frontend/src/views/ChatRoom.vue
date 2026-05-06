<template>
  <div class="telegram-layout">

    <el-image-viewer
        v-if="showViewer"
        :url-list="[previewUrl]"
        @close="closeViewer"
    />

    <!-- 侧边栏 -->
    <div class="sidebar">
      <div class="sidebar-header">
        <el-input
            v-model="searchText"
            :placeholder="t('search')"
            prefix-icon="Search"
            class="search-input"
        />
        <div class="action-btn" @click="openCreateGroup" :title="t('createGroup')">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
            <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
          </svg>
        </div>
        <div class="action-btn action-btn-badge" @click="openNotificationCenter" :title="t('notifications')">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
            <path d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22zm6-6V11a6 6 0 1 0-12 0v5L4 18v1h16v-1l-2-2z"/>
          </svg>
          <span v-if="notificationBadgeCount > 0" class="header-badge">{{ notificationBadgeCount }}</span>
        </div>
        <div class="lang-switch" @click="toggleLanguage" :title="t('switchLangTip')">
          <svg class="lang-icon" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
            <rect x="0" y="0" width="48" height="48" rx="24" :fill="currentLang === 'zh' ? '#ff5252' : '#3390ec'"
                  class="bg-rect"/>
            <g v-if="currentLang === 'en'" fill="white">
              <path d="M14 16h10v3h-7v4h6v3h-6v5h7v3h-10z"/>
              <path
                  d="M26 19h3v1.5a3.5 3.5 0 0 1 3-1.5c2.5 0 4 1.8 4 4.5v10.5h-3v-10c0-1.5-.8-2.3-2.2-2.3-1.5 0-2.5 1-2.5 2.8v9.5h-3z"/>
            </g>
            <g v-else fill="white" transform="translate(11, 11) scale(1.1)">
              <path d="M2 4h20v13h-20z m17 10v-7h-14v7z" fill-rule="evenodd"/>
              <path d="M10.5 0v24h3v-24z"/>
            </g>
          </svg>
        </div>
      </div>

      <div
          ref="contactListRef"
          class="contact-list"
          :class="{ 'with-scroll-actions': showSearchResults && (scrollUi.main.showBackToTop || scrollUi.main.reachedEnd) }"
          @scroll.passive="handleMainSearchScroll"
      >
        <template v-if="showSearchResults">
          <div v-if="searchMatchedChats.length > 0" class="result-section">
            <div class="result-section-title">{{ t('chats') }}</div>
            <div
                v-for="contact in searchMatchedChats"
                :key="contact.id + contact.type"
                class="contact-item"
                :class="{ 'active': currentChatId === contact.id && currentChatType === contact.type }"
                @click="selectChat(contact)"
            >
              <div class="avatar" :style="{ backgroundColor: getAvatarColor(contact.id) }">
                <img v-if="contact.avatar" :src="getConversationAvatarUrl(contact)" class="avatar-image" />
                <svg v-else-if="contact.type === 'group'" viewBox="0 0 24 24" width="24" height="24" fill="white">
                  <path
                      d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
                </svg>
                <span v-else>{{ contact.username.charAt(0).toUpperCase() }}</span>
                <span v-if="contact.type === 'private' && contact.isOnline" class="online-dot"></span>
              </div>

              <div class="contact-info">
                <div class="info-top">
                  <div class="name-with-badge">
                   <span class="username">{{ contact.username }}</span>
                   <span v-if="contact.isTemporary" class="search-tag draft">{{ t('draftChat') }}</span>
                  </div>
                  <div class="item-actions">
                    <button
                        v-if="contact.isTemporary"
                        class="temp-close-btn"
                        type="button"
                        @click.stop="closeTemporaryConversation(contact)"
                        :title="t('closeDraftChat')"
                    >
                      ×
                    </button>
                    <span class="time">{{ getConversationTimeLabel(contact) }}</span>
                  </div>
                </div>
                <div class="info-bottom">
                  <span class="last-message">{{ getConversationPreview(contact) }}</span>
                  <span v-if="contact.unreadCount > 0" class="unread-badge">
                    {{ contact.unreadCount }}
                  </span>
                </div>
              </div>

              <div v-if="contact.type === 'private' && getSearchUserState(contact.id)" class="search-user-actions" @click.stop>
                <button
                    v-if="getSearchUserState(contact.id).relationship_status === 'none'"
                    type="button"
                    class="friend-action-btn primary"
                    @click.stop="sendFriendRequest(getSearchUserState(contact.id))"
                    :disabled="isFriendActionLoading(contact.id)"
                >
                  {{ t('addFriend') }}
                </button>
                <template v-else-if="getSearchUserState(contact.id).relationship_status === 'incoming_pending'">
                  <button
                      type="button"
                      class="friend-action-btn primary"
                      @click.stop="acceptFriendRequest(getSearchUserState(contact.id).friend_request_id, contact.id)"
                      :disabled="isFriendActionLoading(contact.id)"
                  >
                    {{ t('accept') }}
                  </button>
                  <button
                      type="button"
                      class="friend-action-btn ghost"
                      @click.stop="rejectFriendRequest(getSearchUserState(contact.id).friend_request_id, contact.id)"
                      :disabled="isFriendActionLoading(contact.id)"
                  >
                    {{ t('reject') }}
                  </button>
                </template>
                <button
                    v-else-if="getSearchUserState(contact.id).relationship_status === 'outgoing_pending'"
                    type="button"
                    class="friend-action-btn ghost"
                    @click.stop="cancelFriendRequest(getSearchUserState(contact.id).friend_request_id, contact.id)"
                    :disabled="isFriendActionLoading(contact.id)"
                >
                  {{ t('cancelRequest') }}
                </button>
                <span v-else class="search-tag joined friend-tag">{{ t('friend') }}</span>
              </div>
            </div>
          </div>

          <div v-if="discoveredUsers.length > 0" class="result-section">
            <div class="result-section-title">{{ t('users') }}</div>
            <div
                v-for="user in discoveredUsers"
                :key="`user-${user.id}`"
                class="contact-item search-result-item"
                @click="openUserSearchResult(user)"
            >
              <div class="avatar" :style="{ backgroundColor: getAvatarColor(user.id) }">
                <img v-if="user.avatar" :src="getAvatarUrl(user.avatar)" class="avatar-image" />
                <span v-else>{{ user.username.charAt(0).toUpperCase() }}</span>
                <span v-if="user.is_online" class="online-dot"></span>
              </div>

              <div class="contact-info">
                <div class="info-top">
                  <span class="username">{{ user.username }}</span>
                </div>
                <div class="info-bottom">
                  <span class="last-message">{{ user.can_start_chat ? t('startChat') : t('addFriendToChat') }}</span>
                </div>
              </div>

              <div class="search-user-actions" @click.stop>
                <button
                    v-if="user.relationship_status === 'none'"
                    type="button"
                    class="friend-action-btn primary"
                    @click.stop="sendFriendRequest(user)"
                    :disabled="isFriendActionLoading(user.id)"
                >
                  {{ t('addFriend') }}
                </button>
                <template v-else-if="user.relationship_status === 'incoming_pending'">
                  <button
                      type="button"
                      class="friend-action-btn primary"
                      @click.stop="acceptFriendRequest(user.friend_request_id, user.id)"
                      :disabled="isFriendActionLoading(user.id)"
                  >
                    {{ t('accept') }}
                  </button>
                  <button
                      type="button"
                      class="friend-action-btn ghost"
                      @click.stop="rejectFriendRequest(user.friend_request_id, user.id)"
                      :disabled="isFriendActionLoading(user.id)"
                  >
                    {{ t('reject') }}
                  </button>
                </template>
                <button
                    v-else-if="user.relationship_status === 'outgoing_pending'"
                    type="button"
                    class="friend-action-btn ghost"
                    @click.stop="cancelFriendRequest(user.friend_request_id, user.id)"
                    :disabled="isFriendActionLoading(user.id)"
                >
                  {{ t('cancelRequest') }}
                </button>
                <span v-else class="search-tag joined friend-tag">{{ t('friend') }}</span>
              </div>
            </div>
            <div v-if="searchResults.usersLoadingMore" class="search-skeleton-list compact-skeleton-list">
              <div v-for="row in 2" :key="`user-skeleton-${row}`" class="search-skeleton-item">
                <div class="skeleton-avatar"></div>
                <div class="skeleton-content">
                  <div class="skeleton-line medium"></div>
                  <div class="skeleton-line short"></div>
                </div>
              </div>
            </div>
            <div v-else-if="searchResults.usersPaginationTouched && !searchResults.usersHasMore" class="subtle-end-hint">{{ t('noMoreResults') }}</div>
          </div>
          <div v-if="searchResults.usersLoadingMore && discoveredUsers.length === 0" class="search-skeleton-list compact-skeleton-list">
            <div v-for="row in 2" :key="`user-skeleton-fallback-${row}`" class="search-skeleton-item">
              <div class="skeleton-avatar"></div>
              <div class="skeleton-content">
                <div class="skeleton-line medium"></div>
                <div class="skeleton-line short"></div>
              </div>
            </div>
          </div>

          <div v-if="searchGroupEntries.length > 0" class="result-section">
            <div class="result-section-title">{{ t('groups') }}</div>
            <div
                v-for="group in searchGroupEntries"
                :key="`group-${group.id}`"
                class="contact-item search-result-item"
                :class="{ 'active': currentChatId === group.id && currentChatType === 'group' }"
                @click="openGroupSearchResult(group)"
            >
              <div class="avatar" :style="{ backgroundColor: getAvatarColor(group.id) }">
                <img v-if="group.avatar" :src="getGroupAvatarUrl(group.avatar)" class="avatar-image" />
                <svg v-else viewBox="0 0 24 24" width="24" height="24" fill="white">
                  <path
                      d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
                </svg>
              </div>

              <div class="contact-info">
                <div class="info-top">
                  <span class="username">{{ group.name }}</span>
                  <span class="search-tag" :class="group.is_member ? 'joined' : 'locked'">
                    {{ group.is_member ? t('joined') : (group.invite_status === 'pending' ? t('invited') : (group.join_request_status === 'pending' ? t('requested') : t('notJoined'))) }}
                  </span>
                  <span v-if="group.conversation?.lastTime || getDraftMetaForConversation(group.id, 'group').updatedAt" class="time">
                    {{ group.conversation ? getConversationTimeLabel(group.conversation) : formatSidebarTime(getDraftMetaForConversation(group.id, 'group').updatedAt) }}
                  </span>
                </div>
                <div class="info-bottom">
                  <span class="last-message">
                    {{ group.conversation ? getConversationPreview(group.conversation) : `${group.member_count} ${t('membersCount')} · ${group.is_member ? t('openJoinedGroup') : t('requestToJoin')}` }}
                  </span>
                  <span v-if="group.conversation?.unreadCount > 0" class="unread-badge">
                    {{ group.conversation.unreadCount }}
                  </span>
                </div>
              </div>

              <div v-if="!group.is_member" class="search-user-actions" @click.stop>
                <template v-if="group.invite_status === 'pending'">
                  <button type="button" class="friend-action-btn primary" @click.stop="acceptGroupInvite(group.invite_id, group.id)" :disabled="isGroupActionLoading(group.id)">
                    {{ t('accept') }}
                  </button>
                  <button type="button" class="friend-action-btn ghost" @click.stop="rejectGroupInvite(group.invite_id, group.id)" :disabled="isGroupActionLoading(group.id)">
                    {{ t('reject') }}
                  </button>
                </template>
                <button
                    v-else-if="group.join_request_status === 'pending'"
                    type="button"
                    class="friend-action-btn ghost"
                    @click.stop="cancelGroupJoinRequest(group.join_request_id, group.id)"
                    :disabled="isGroupActionLoading(group.id)"
                >
                  {{ t('cancelRequest') }}
                </button>
                <button
                    v-else
                    type="button"
                    class="friend-action-btn primary"
                    @click.stop="createGroupJoinRequest(group.id)"
                    :disabled="isGroupActionLoading(group.id)"
                >
                  {{ t('applyToJoin') }}
                </button>
              </div>
            </div>
            <div v-if="searchResults.groupsLoadingMore" class="search-skeleton-list compact-skeleton-list">
              <div v-for="row in 2" :key="`group-skeleton-${row}`" class="search-skeleton-item">
                <div class="skeleton-avatar"></div>
                <div class="skeleton-content">
                  <div class="skeleton-line medium"></div>
                  <div class="skeleton-line short"></div>
                </div>
              </div>
            </div>
            <div v-else-if="searchResults.groupsPaginationTouched && !searchResults.groupsHasMore" class="subtle-end-hint">{{ t('noMoreResults') }}</div>
          </div>
          <div v-if="searchResults.groupsLoadingMore && searchGroupEntries.length === 0" class="search-skeleton-list compact-skeleton-list">
            <div v-for="row in 2" :key="`group-skeleton-fallback-${row}`" class="search-skeleton-item">
              <div class="skeleton-avatar"></div>
              <div class="skeleton-content">
                <div class="skeleton-line medium"></div>
                <div class="skeleton-line short"></div>
              </div>
            </div>
          </div>

          <div
              v-if="searchResults.loading && searchMatchedChats.length === 0 && discoveredUsers.length === 0 && searchGroupEntries.length === 0"
              class="search-skeleton-list"
          >
            <div v-for="row in 4" :key="`main-search-skeleton-${row}`" class="search-skeleton-item">
              <div class="skeleton-avatar"></div>
              <div class="skeleton-content">
                <div class="skeleton-line long"></div>
                <div class="skeleton-line medium"></div>
              </div>
              <div class="skeleton-time"></div>
            </div>
          </div>
          <div v-else-if="searchResults.error" class="empty-hint">{{ searchResults.error }}</div>
          <div
              v-else-if="searchMatchedChats.length === 0 && discoveredUsers.length === 0 && searchGroupEntries.length === 0"
              class="empty-hint"
          >
            {{ t('searchEmpty') }}
          </div>

          <div v-if="showSearchResults && (scrollUi.main.showBackToTop || scrollUi.main.reachedEnd)" class="list-floating-actions main-list-actions">
            <div v-if="scrollUi.main.reachedEnd" class="scroll-end-pill">{{ t('reachedEnd') }}</div>
            <button
                v-if="scrollUi.main.showBackToTop"
                type="button"
                class="scroll-top-btn"
                @click="scrollListToTop('main')"
            >
              {{ t('backToTop') }}
            </button>
          </div>
        </template>

        <template v-else>
          <div v-if="contactList.length === 0" class="empty-hint sidebar-empty-hint">{{ t('sidebarEmpty') }}</div>
          <div
              v-for="contact in filteredContacts"
              :key="contact.id + contact.type"
              class="contact-item"
              :class="{ 'active': currentChatId === contact.id && currentChatType === contact.type }"
              @click="selectChat(contact)"
          >
            <div class="avatar" :style="{ backgroundColor: getAvatarColor(contact.id) }">
              <img v-if="contact.avatar" :src="getConversationAvatarUrl(contact)" class="avatar-image" />
              <svg v-else-if="contact.type === 'group'" viewBox="0 0 24 24" width="24" height="24" fill="white">
                <path
                    d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
              </svg>
              <span v-else>{{ contact.username.charAt(0).toUpperCase() }}</span>
              <span v-if="contact.type === 'private' && contact.isOnline" class="online-dot"></span>
            </div>

            <div class="contact-info">
              <div class="info-top">
                <div class="name-with-badge">
                   <span class="username">{{ contact.username }}</span>
                   <span v-if="contact.isTemporary" class="search-tag draft">{{ t('draftChat') }}</span>
                </div>
                <div class="item-actions">
                  <button
                      v-if="contact.isTemporary"
                      class="temp-close-btn"
                      type="button"
                      @click.stop="closeTemporaryConversation(contact)"
                      :title="t('closeDraftChat')"
                    >
                      ×
                    </button>
                  <span class="time">{{ getConversationTimeLabel(contact) }}</span>
                </div>
              </div>
              <div class="info-bottom">
                <span class="last-message">{{ getConversationPreview(contact) }}</span>
                <span v-if="contact.unreadCount > 0" class="unread-badge">
                  {{ contact.unreadCount }}
                </span>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div class="my-profile">
        <el-dropdown trigger="click" placement="top-start" @command="handleProfileCommand">
          <div class="profile-card">
            <div class="mini-avatar" :style="{ backgroundColor: getAvatarColor(myUserIdState) }">
              <img v-if="myAvatar" :src="getAvatarUrl(myAvatar)" class="avatar-image" />
              <span v-else>{{ myUsername.charAt(0).toUpperCase() }}</span>
            </div>
            <div class="profile-info">
              <div class="profile-name">{{ myUsername }}</div>
              <div class="profile-id">ID: {{ myUserIdState }}</div>
            </div>
            <div class="profile-settings-icon">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                <path
                    d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.488.488 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 0 0-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
              </svg>
            </div>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="settings"><span>⚙️ {{ t('settings') }}</span></el-dropdown-item>
              <el-dropdown-item command="logout" divided>
                <span class="logout-text">🚪 {{ t('logout') }}</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 聊天主区 -->
    <div class="chat-main">
      <template v-if="currentChatId">
        <div class="chat-header">
          <div
              class="header-info"
              @click="currentChatType === 'group' ? openGroupManage() : null"
              :class="{ 'cursor-pointer': currentChatType === 'group' }"
          >

            <span class="header-name">{{ currentChatUser?.username }}</span>
               <span
                   v-if="currentChatType === 'private'"
                   class="header-status"
                  :class="{ 'online-text': currentChatUser?.isOnline }"
               >
               {{ currentChatUser?.canChat === false ? t('privateChatLocked') : (currentChatUser?.isTemporary ? t('draftChat') : (currentChatUser?.isOnline ? t('online') : t('offline'))) }}
               </span>
           </div>
        </div>

        <div class="messages-area" ref="messagesRef">
          <div
              v-for="(msg, index) in messages"
              :key="index"
              class="message-row"
              :class="{ 'my-message': msg.from === myUserId }"
          >
            <div
                v-if="msg.from !== myUserId"
                class="msg-avatar small"
                :style="{ backgroundColor: getAvatarColor(msg.from) }"
            >
              <img v-if="msg.avatar" :src="getAvatarUrl(msg.avatar)" class="avatar-image" />
              <span v-else>{{ getMessageSenderAvatar(msg) }}</span>
            </div>

             <div
                 class="message-bubble"
                 :class="{
                   'group-peer-bubble': isIncomingGroupMessage(msg),
                   'media-bubble': isImageMessage(msg),
                   'file-bubble': getMsgType(msg) === 'file'
                 }"
             >
              <div v-if="shouldShowGroupBubbleHeader(msg)" class="bubble-header">
                <span class="msg-sender-name" :style="getGroupSenderNameStyle(msg)">
                  {{ msg.username }}
                </span>
              </div>

              <div v-if="isMessageRecalled(msg)" class="message-content recalled-message-content">{{ getRecalledMessageText(msg) }}</div>
              <div v-else-if="getMsgType(msg) === 'text'" class="message-content">{{ msg.content }}</div>
              <div v-else-if="getMsgType(msg) === 'image'" class="message-image">
                <img v-if="getFileUrl(msg.content)" :src="getFileUrl(msg.content)" alt="image" @click.stop="previewImage(msg.content)" />
                <div v-else class="image-loading-placeholder">
                  <span v-if="isAttachmentLoadFailed(msg.content)" class="load-failed-text">{{ t('imageLoadFailed') }}</span>
                  <span v-else class="loading-spinner-text">{{ t('imageLoading') }}</span>
                </div>
              </div>
              <div v-else class="message-file">
                <div class="file-icon">📄</div>
                <div class="file-info">
                  <a :href="getFileUrl(msg.content)" target="_blank" rel="noopener noreferrer" download class="file-name">
                    {{ getFileName(msg.content) }}
                  </a>
                </div>
              </div>

              <div v-if="getMessageTimeLabel(msg)" class="bubble-footer" :class="{ 'media-footer': isImageMessage(msg) }">
                <span>{{ getMessageTimeLabel(msg) }}</span>
                <div v-if="!isMessageRecalled(msg) && msg.from === myUserId && currentChatType === 'group'" class="bubble-read-status" @click="openReadReceiptPopover($event, msg)" :title="getGroupReadSummaryTitle(msg)">
                  <span class="bubble-status-text">{{ getDeliveryStatusLabel(msg) }}</span>
                  <div v-if="getGroupReadReaders(msg).length" class="read-avatars">
                    <div
                      v-for="(reader, idx) in getGroupReadReaders(msg).slice(0, 3)"
                      :key="reader.userId"
                      class="read-avatar"
                      :style="{ backgroundColor: reader.color, zIndex: 10 - idx, marginLeft: idx === 0 ? '0' : '-5px' }"
                      :title="reader.username"
                    >
                      <img v-if="reader.avatar" :src="reader.avatar" class="avatar-image" />
                      <span v-else>{{ reader.initials }}</span>
                    </div>
                  </div>
                </div>
                <span v-else-if="!isMessageRecalled(msg) && msg.from === myUserId" class="bubble-status-text" :title="getGroupReadSummaryTitle(msg)">{{ getDeliveryStatusLabel(msg) }}</span>
                <button v-if="!isMessageRecalled(msg) && msg.from === myUserId && msg.deliveryStatus === 'failed'" type="button" class="bubble-retry-btn" @click.stop="retryOutgoingMessage(msg)">
                  {{ t('retry') }}
                </button>
                <button v-if="canRecallMessage(msg)" type="button" class="bubble-recall-btn" @click.stop="recallMessage(msg)">
                  {{ t('recallMessage') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <Teleport to="body">
          <div v-if="readReceiptPopover.visible" class="read-receipt-popover" :style="{ top: readReceiptPopover.y + 'px', left: readReceiptPopover.x + 'px' }" @click.stop>
            <div class="popover-header">{{ t('readBy') }}</div>
            <div class="popover-list">
              <div v-for="reader in readReceiptPopover.readers" :key="reader.userId" class="popover-reader">
                <div class="popover-avatar" :style="{ backgroundColor: reader.color }">
                  <img v-if="reader.avatar" :src="reader.avatar" class="avatar-image" />
                  <span v-else>{{ reader.initials }}</span>
                </div>
                <div class="popover-info">
                  <div class="popover-name">{{ reader.username }}</div>
                  <div v-if="reader.readAt" class="popover-time">{{ formatLastSeenLabel(reader.readAt) }}</div>
                </div>
              </div>
            </div>
          </div>
          <div v-if="readReceiptPopover.visible" class="read-receipt-overlay" @click="closeReadReceiptPopover"></div>
        </Teleport>

        <div class="input-area">
          <input type="file" ref="fileInput" class="hidden-file-input" @change="handleFileUpload"/>
          <div class="attach-btn" :class="{ 'disabled-action': !currentChatCanSend }" @click="triggerUpload" :title="t('sendFileTip')">
            <svg viewBox="0 0 24 24" width="24" height="24" class="icon">
              <path
                  d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5a2.5 2.5 0 0 0 5 0V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"
                  fill="currentColor"/>
            </svg>
          </div>
          <textarea
              v-model="inputText"
              :placeholder="t('inputPlaceholder')"
              @keydown.enter.prevent="sendMessage"
              rows="1"
              class="chat-input"
              :disabled="!currentChatCanSend"
          ></textarea>
          <div
              class="send-icon-btn"
              @click="sendMessage"
              :class="{ 'active': inputText.trim() && currentChatCanSend, 'disabled-action': !currentChatCanSend }"
              :title="t('send')"
          >
            <svg viewBox="0 0 24 24" width="24" height="24" class="icon">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" fill="currentColor"/>
            </svg>
          </div>
        </div>
      </template>

      <div v-else class="empty-state">
        <div class="empty-content">
          <p>{{ t('emptyState') }}</p>
        </div>
      </div>
    </div>

    <!-- 账户设置弹窗 -->
    <el-dialog
        v-model="settingsVisible"
        :title="t('settings')"
        width="400px"
        align-center
        class="tg-dialog"
        :show-close="false"
        @close="clearPendingAvatarSelection('profile')"
    >
      <div class="tg-dialog-content">
        <el-tabs v-model="activeTab" class="tg-tabs">
          <el-tab-pane :label="t('profile')" name="profile">
            <div class="avatar-section">
              <input type="file" ref="avatarInputRef" class="hidden-file-input" @change="handleAvatarChange" accept="image/*" />
              <div class="large-avatar" :style="{ backgroundColor: getAvatarColor(myUserId) }" @click="triggerAvatarUpload" style="cursor: pointer;" :title="currentLang === 'en' ? 'Click to change avatar' : '点击修改头像'">
                <img v-if="pendingAvatarUrl || myAvatar" :src="pendingAvatarUrl || getAvatarUrl(myAvatar)" class="avatar-image" />
                <span v-else>{{ myUsername.charAt(0).toUpperCase() }}</span>
              </div>
            </div>
            <div class="input-group">
              <label>{{ t('username') }}</label>
              <el-input
                  v-model="settingsForm.newUsername"
                  :placeholder="t('newUsernamePlaceholder')"
                  class="tg-input"
              />
            </div>
            <div class="dialog-actions">
              <button class="tg-btn primary" @click="saveProfile" :disabled="loading">{{ t('save') }}</button>
            </div>
          </el-tab-pane>
          <el-tab-pane :label="t('security')" name="security">
            <div class="input-group">
              <label>{{ t('oldPassword') }}</label>
              <el-input v-model="settingsForm.oldPassword" type="password" show-password class="tg-input" />
            </div>
            <div class="input-group">
              <label>{{ t('newPassword') }}</label>
              <el-input v-model="settingsForm.newPassword" type="password" show-password class="tg-input" />
            </div>
            <div class="dialog-actions">
              <button class="tg-btn danger" @click="updatePassword" :disabled="loading">
                {{ t('changePassword') }}
              </button>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>

    <el-dialog v-model="logoutConfirmVisible" :title="t('logoutConfirmTitle')" width="360px" align-center class="tg-dialog">
      <div class="tg-dialog-content">
        <div class="confirm-dialog-text">{{ t('logoutConfirmMessage') }}</div>
        <div class="dialog-footer-actions">
          <button class="tg-btn ghost" type="button" @click="logoutConfirmVisible = false" :disabled="logoutPending">{{ t('cancel') }}</button>
          <button class="tg-btn danger" type="button" @click="handleLogout" :disabled="logoutPending">{{ t('logoutConfirmAction') }}</button>
        </div>
      </div>
    </el-dialog>

    <!-- 裁剪头像弹窗 -->
    <el-dialog
        v-model="cropperDialogVisible"
        :title="currentLang === 'en' ? 'Crop Avatar' : '裁剪头像'"
        width="400px"
        align-center
        class="tg-dialog"
        :close-on-click-modal="false"
        @close="cancelCrop"
    >
      <div class="cropper-container" style="height: 300px; width: 100%;">
        <img ref="cropperImgRef" :src="currentCropImageUrl" style="max-width: 100%; display: block;" crossorigin="anonymous" />
      </div>
      <div class="dialog-actions" style="margin-top: 20px; display: flex; gap: 12px; flex-direction: row; justify-content: flex-end;">
        <button class="tg-btn" style="background: #e4e6eb; color: #000; width: auto; margin-top: 0; padding: 8px 24px; border-radius: 20px;" @click="cancelCrop" :disabled="isCropping">{{ t('cancel') }}</button>
        <button class="tg-btn primary" style="width: auto; margin-top: 0; padding: 8px 24px; border-radius: 20px;" @click="confirmAvatarCrop" :disabled="isCropping">{{ t('save') }}</button>
      </div>
    </el-dialog>
    <!-- 通知中心弹窗 -->
    <el-dialog v-model="notificationCenterVisible" :title="t('notifications')" width="460px" align-center class="tg-dialog">
      <div class="tg-dialog-content">
        <el-tabs v-model="notificationCenterTab" class="tg-tabs">
          <el-tab-pane :label="t('friendsHub')" name="friends">
            <el-tabs v-model="friendRequestsTab" class="tg-tabs nested-tabs">
              <el-tab-pane :label="`${t('incomingRequests')} (${incomingFriendRequests.length})`" name="incoming">
                <div class="friend-request-list">
                  <div v-if="friendRequestsLoading" class="picker-skeleton-list">
                    <div v-for="row in 3" :key="`incoming-friend-skeleton-${row}`" class="picker-skeleton-item">
                      <div class="skeleton-avatar small"></div>
                      <div class="skeleton-line medium"></div>
                    </div>
                  </div>
                  <div v-else-if="incomingFriendRequests.length === 0" class="empty-hint">{{ t('noIncomingRequests') }}</div>
                  <div v-for="request in incomingFriendRequests" :key="`incoming-${request.id}`" class="friend-request-item">
                    <div class="mini-avatar" :style="{ backgroundColor: getAvatarColor(request.user.id) }">
                      {{ request.user.username.charAt(0).toUpperCase() }}
                    </div>
                    <div class="friend-request-info">
                      <div class="friend-request-name">{{ request.user.username }}</div>
                    </div>
                    <div class="friend-request-actions">
                      <button class="friend-action-btn primary" @click="acceptFriendRequest(request.id, request.user.id)" :disabled="isFriendActionLoading(request.user.id)">
                        {{ t('accept') }}
                      </button>
                      <button class="friend-action-btn ghost" @click="rejectFriendRequest(request.id, request.user.id)" :disabled="isFriendActionLoading(request.user.id)">
                        {{ t('reject') }}
                      </button>
                    </div>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane :label="`${t('outgoingRequests')} (${outgoingFriendRequests.length})`" name="outgoing">
                <div class="friend-request-list">
                  <div v-if="friendRequestsLoading" class="picker-skeleton-list">
                    <div v-for="row in 3" :key="`outgoing-friend-skeleton-${row}`" class="picker-skeleton-item">
                      <div class="skeleton-avatar small"></div>
                      <div class="skeleton-line medium"></div>
                    </div>
                  </div>
                  <div v-else-if="outgoingFriendRequests.length === 0" class="empty-hint">{{ t('noOutgoingRequests') }}</div>
                  <div v-for="request in outgoingFriendRequests" :key="`outgoing-${request.id}`" class="friend-request-item">
                    <div class="mini-avatar" :style="{ backgroundColor: getAvatarColor(request.user.id) }">
                      {{ request.user.username.charAt(0).toUpperCase() }}
                    </div>
                    <div class="friend-request-info">
                      <div class="friend-request-name">{{ request.user.username }}</div>
                    </div>
                    <div class="friend-request-actions">
                      <button class="friend-action-btn ghost" @click="cancelFriendRequest(request.id, request.user.id)" :disabled="isFriendActionLoading(request.user.id)">
                        {{ t('cancelRequest') }}
                      </button>
                    </div>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane :label="`${t('friendsList')} (${friendsList.length})`" name="friends-list">
                <div class="friend-request-list">
                  <div v-if="friendRequestsLoading" class="picker-skeleton-list">
                    <div v-for="row in 3" :key="`friends-skeleton-${row}`" class="picker-skeleton-item">
                      <div class="skeleton-avatar small"></div>
                      <div class="skeleton-line medium"></div>
                    </div>
                  </div>
                  <div v-else-if="friendsList.length === 0" class="empty-hint">{{ t('noFriendsYet') }}</div>
                  <div v-for="friend in friendsList" :key="`friend-${friend.id}`" class="friend-request-item">
                    <div class="mini-avatar" :style="{ backgroundColor: getAvatarColor(friend.id) }">
                      {{ friend.username.charAt(0).toUpperCase() }}
                    </div>
                    <div class="friend-request-info">
                      <div class="friend-request-name">{{ friend.username }}</div>
                    </div>
                    <div class="friend-request-actions">
                      <button class="friend-action-btn ghost danger-text" @click="removeFriend(friend.id)" :disabled="isFriendActionLoading(friend.id)">
                        {{ t('removeFriendAction') }}
                      </button>
                    </div>
                  </div>
                </div>
              </el-tab-pane>
            </el-tabs>
          </el-tab-pane>

          <el-tab-pane :label="`${t('groupRequests')} (${groupAccessBadgeCount})`" name="groups">
            <el-tabs v-model="groupAccessTab" class="tg-tabs nested-tabs">
              <el-tab-pane :label="`${t('receivedInvites')} (${receivedGroupInvites.length})`" name="invites">
                <div class="friend-request-list">
                  <div v-if="groupAccessLoading" class="picker-skeleton-list">
                    <div v-for="row in 3" :key="`group-invite-skeleton-${row}`" class="picker-skeleton-item">
                      <div class="skeleton-avatar small"></div>
                      <div class="skeleton-line medium"></div>
                    </div>
                  </div>
                  <div v-else-if="groupAccessError" class="empty-hint">{{ groupAccessError }}</div>
                  <div v-else-if="receivedGroupInvites.length === 0" class="empty-hint">{{ t('noGroupInvites') }}</div>
                  <div v-for="invite in receivedGroupInvites" :key="`group-invite-${invite.id}`" class="friend-request-item">
                    <div class="mini-avatar" :style="{ backgroundColor: getAvatarColor(invite.group_id) }">
                      <img v-if="invite.group_avatar" :src="getGroupAvatarUrl(invite.group_avatar)" class="avatar-image" />
                      <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="white">
                        <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
                      </svg>
                    </div>
                    <div class="friend-request-info">
                      <div class="friend-request-name">{{ invite.group_name }}</div>
                      <div class="request-subtitle">{{ invite.inviter.username }}</div>
                    </div>
                    <div class="friend-request-actions">
                      <button class="friend-action-btn primary" @click="acceptGroupInvite(invite.id, invite.group_id)" :disabled="isGroupActionLoading(invite.group_id)">
                        {{ t('accept') }}
                      </button>
                      <button class="friend-action-btn ghost" @click="rejectGroupInvite(invite.id, invite.group_id)" :disabled="isGroupActionLoading(invite.group_id)">
                        {{ t('reject') }}
                      </button>
                    </div>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane :label="`${t('myJoinRequests')} (${myGroupJoinRequests.length})`" name="requests">
                <div class="friend-request-list">
                  <div v-if="groupAccessLoading" class="picker-skeleton-list">
                    <div v-for="row in 3" :key="`group-request-skeleton-${row}`" class="picker-skeleton-item">
                      <div class="skeleton-avatar small"></div>
                      <div class="skeleton-line medium"></div>
                    </div>
                  </div>
                  <div v-else-if="groupAccessError" class="empty-hint">{{ groupAccessError }}</div>
                  <div v-else-if="myGroupJoinRequests.length === 0" class="empty-hint">{{ t('noJoinRequests') }}</div>
                  <div v-for="request in myGroupJoinRequests" :key="`group-request-${request.id}`" class="friend-request-item">
                    <div class="mini-avatar" :style="{ backgroundColor: getAvatarColor(request.group_id) }">
                      <img v-if="request.group_avatar" :src="getGroupAvatarUrl(request.group_avatar)" class="avatar-image" />
                      <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="white">
                        <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
                      </svg>
                    </div>
                    <div class="friend-request-info">
                      <div class="friend-request-name">{{ request.group_name }}</div>
                      <div class="request-subtitle">{{ request.note || t('requestToJoin') }}</div>
                    </div>
                    <div class="friend-request-actions">
                      <button class="friend-action-btn ghost" @click="cancelGroupJoinRequest(request.id, request.group_id)" :disabled="isGroupActionLoading(request.group_id)">
                        {{ t('cancelRequest') }}
                      </button>
                    </div>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane :label="`${t('ownedJoinRequests')} (${ownedGroupJoinRequests.length})`" name="owned">
                <div class="friend-request-list">
                  <div v-if="groupAccessLoading" class="picker-skeleton-list">
                    <div v-for="row in 3" :key="`owned-group-request-skeleton-${row}`" class="picker-skeleton-item">
                      <div class="skeleton-avatar small"></div>
                      <div class="skeleton-line medium"></div>
                    </div>
                  </div>
                  <div v-else-if="groupAccessError" class="empty-hint">{{ groupAccessError }}</div>
                  <div v-else-if="ownedGroupJoinRequests.length === 0" class="empty-hint">{{ t('noPendingGroupRequests') }}</div>
                  <div v-for="request in ownedGroupJoinRequests" :key="`owned-group-request-${request.id}`" class="friend-request-item">
                    <div class="mini-avatar" :style="{ backgroundColor: getAvatarColor(request.requester.id) }">
                      <img v-if="request.requester.avatar" :src="getAvatarUrl(request.requester.avatar)" class="avatar-image" />
                      <span v-else>{{ request.requester.username.charAt(0).toUpperCase() }}</span>
                    </div>
                    <div class="friend-request-info">
                      <div class="friend-request-name">{{ request.requester.username }}</div>
                      <div class="request-subtitle">{{ request.group_name }} · {{ request.note || t('requestToJoin') }}</div>
                    </div>
                    <div class="friend-request-actions">
                      <button class="friend-action-btn primary" @click="approveGroupJoinRequest(request.id, request.group_id)" :disabled="isGroupActionLoading(request.id)">
                        {{ t('accept') }}
                      </button>
                      <button class="friend-action-btn ghost" @click="rejectGroupJoinRequest(request.id, request.group_id)" :disabled="isGroupActionLoading(request.id)">
                        {{ t('reject') }}
                      </button>
                    </div>
                  </div>
                </div>
              </el-tab-pane>
            </el-tabs>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>

    <!-- 创建群组弹窗 -->
    <el-dialog v-model="createGroupVisible" :title="t('createGroup')" width="380px" align-center class="tg-dialog" @close="clearPendingAvatarSelection('create-group')">
      <div class="tg-dialog-content">
        <div class="avatar-section">
          <input type="file" ref="createGroupAvatarInputRef" class="hidden-file-input" @change="handleAvatarChange" accept="image/*" />
          <div
            class="large-avatar"
            :style="{ backgroundColor: getAvatarColor(myUserId || 0), cursor: 'pointer' }"
            @click="triggerAvatarUpload('create-group')"
            :title="currentLang === 'en' ? 'Click to set group avatar' : '点击设置群头像'"
          >
            <img v-if="pendingGroupAvatarUrl" :src="pendingGroupAvatarUrl" class="avatar-image" />
            <svg v-else viewBox="0 0 24 24" width="32" height="32" fill="white">
              <path
                d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
            </svg>
          </div>
        </div>
        <div class="input-group">
          <el-input
              v-model="newGroupName"
              :placeholder="t('groupNamePlaceholder')"
              class="tg-input"
          />
        </div>
        <div class="input-group compact-input-group">
          <el-input
              v-model="createGroupMemberSearch"
              :placeholder="t('searchUsersForGroup')"
              class="tg-input"
          />
        </div>
        <div class="section-title">{{ t('selectMembers') }}</div>
        <div
            ref="createGroupListRef"
            class="user-select-list"
            :class="{ 'with-scroll-actions': createGroupVisible && (scrollUi.create.showBackToTop || scrollUi.create.reachedEnd) }"
            @scroll.passive="handleCreateGroupScroll"
        >
          <div
              v-for="user in filteredCreateGroupCandidates"
              :key="user.id"
              class="user-select-item"
              @click="toggleSelection(user.id)"
          >
            <div class="mini-avatar" :style="{ backgroundColor: getAvatarColor(user.id) }">
              {{ user.username.charAt(0).toUpperCase() }}
            </div>
            <div class="select-name">{{ user.username }}</div>
            <el-checkbox v-model="selectedMembers" :label="user.id" @click.stop class="pointer-events-none">
              &nbsp;
            </el-checkbox>
          </div>
          <div v-if="createGroupSearchLoading || createGroupSearchLoadingMore" class="picker-skeleton-list">
            <div v-for="row in 3" :key="`create-picker-skeleton-${row}`" class="picker-skeleton-item">
              <div class="skeleton-avatar small"></div>
              <div class="skeleton-line medium"></div>
            </div>
          </div>
          <div v-else-if="createGroupSearchError" class="empty-hint">{{ createGroupSearchError }}</div>
          <div v-else-if="filteredCreateGroupCandidates.length === 0" class="empty-hint">{{ t('createGroupSearchEmpty') }}</div>
          <div
              v-else-if="createGroupMemberSearch.trim() && createGroupSearchPaginationTouched && !createGroupSearchHasMore"
              class="subtle-end-hint"
          >
            {{ t('noMoreResults') }}
          </div>

          <div v-if="createGroupVisible && (scrollUi.create.showBackToTop || scrollUi.create.reachedEnd)" class="list-floating-actions picker-list-actions">
            <div v-if="scrollUi.create.reachedEnd" class="scroll-end-pill">{{ t('reachedEnd') }}</div>
            <button
                v-if="scrollUi.create.showBackToTop"
                type="button"
                class="scroll-top-btn"
                @click="scrollListToTop('create')"
            >
              {{ t('backToTop') }}
            </button>
          </div>
        </div>
        <div class="dialog-footer-actions">
          <button class="tg-btn ghost" @click="createGroupVisible = false">{{ t('cancel') }}</button>
          <button class="tg-btn primary" @click="submitCreateGroup">{{ t('create') }}</button>
        </div>
      </div>
    </el-dialog>

    <!-- 群组管理弹窗 -->
    <el-dialog v-model="groupManageVisible" :title="t('manageGroup')" width="400px" align-center class="tg-dialog" @close="clearPendingAvatarSelection('group')">
      <div class="tg-dialog-content">
        <div class="avatar-section">
          <input type="file" ref="groupAvatarInputRef" class="hidden-file-input" @change="handleAvatarChange" accept="image/*" />
          <div
            class="large-avatar"
            :style="{ backgroundColor: getAvatarColor(currentChatId), cursor: isGroupOwner ? 'pointer' : 'default' }"
            @click="isGroupOwner ? triggerAvatarUpload('group') : null"
            :title="isGroupOwner ? (currentLang === 'en' ? 'Click to change group avatar' : '点击修改群头像') : ''"
          >
            <img v-if="pendingGroupAvatarUrl || currentGroupAvatar" :src="pendingGroupAvatarUrl || getGroupAvatarUrl(currentGroupAvatar)" class="avatar-image" />
            <svg v-else viewBox="0 0 24 24" width="32" height="32" fill="white">
              <path
                  d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
            </svg>
          </div>
        </div>
        <div class="input-group">
          <label>{{ t('groupName') }}</label>
          <el-input v-model="editingGroupName" class="tg-input" :readonly="!isGroupOwner"/>
        </div>

        <div class="section-header-row">
          <div class="section-title" style="margin-bottom: 0;">{{ t('members') }} ({{ groupMembers.length }})</div>
          <div v-if="isGroupOwner" style="display: flex; gap: 12px; align-items: center;">
            <div class="add-member-btn secondary-action" @click="openNotificationCenter('groups', 'owned')">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 14h-2v-2h2zm0-4h-2V7h2z"/>
            </svg>
              {{ t('openRequests') }}
            </div>
            <div class="add-member-btn" @click="openInviteDialog">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
            </svg>
            {{ t('add') }}
            </div>
          </div>
        </div>

        <div class="user-select-list">
          <div v-for="member in groupMembers" :key="member.id" class="user-select-item member-item">
            <div class="mini-avatar" :style="{ backgroundColor: getAvatarColor(member.id) }">
              <img v-if="member.avatar" :src="getAvatarUrl(member.avatar)" class="avatar-image" />
              <span v-else>{{ member.username.charAt(0).toUpperCase() }}</span>
            </div>
            <div class="select-name">
              {{ member.username }}
              <span v-if="member.role === 'owner'" class="role-badge owner">{{ t('owner') }}</span>
            </div>
            <div
                v-if="isGroupOwner && member.role !== 'owner'"
                class="kick-btn"
                @click="kickMember(member.id)"
                :title="t('removeMember')"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="#ff595a">
                <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
              </svg>
            </div>
          </div>
        </div>

        <div class="dialog-footer-actions group-manage-actions">
          <button v-if="isGroupOwner" class="tg-btn danger" @click="disbandGroup">{{ t('disbandGroup') }}</button>
          <button v-if="isGroupOwner" class="tg-btn primary" @click="updateGroup">{{ t('save') }}</button>
        </div>
      </div>
    </el-dialog>

    <!-- 邀请成员弹窗 -->
    <el-dialog v-model="inviteVisible" :title="t('inviteMembers')" width="380px" align-center class="tg-dialog">
      <div class="tg-dialog-content">
        <div class="input-group compact-input-group">
          <el-input
              v-model="inviteSearch"
              :placeholder="t('searchInviteMembers')"
              class="tg-input"
          />
        </div>
        <div
            ref="inviteListRef"
            class="user-select-list"
            :class="{ 'with-scroll-actions': inviteVisible && (scrollUi.invite.showBackToTop || scrollUi.invite.reachedEnd) }"
            @scroll.passive="handleInviteScroll"
        >
          <div
              v-for="user in filteredAvailableContacts"
              :key="user.id"
              class="user-select-item"
              @click="toggleInviteSelection(user.id)"
          >
            <div class="mini-avatar" :style="{ backgroundColor: getAvatarColor(user.id) }">
              {{ user.username.charAt(0).toUpperCase() }}
            </div>
            <div class="select-name">{{ user.username }}</div>
            <el-checkbox v-model="inviteSelection" :label="user.id" @click.stop class="pointer-events-none">
              &nbsp;
            </el-checkbox>
          </div>
          <div v-if="inviteSearchLoading || inviteSearchLoadingMore || inviteAccessLoading" class="picker-skeleton-list">
            <div v-for="row in 3" :key="`invite-picker-skeleton-${row}`" class="picker-skeleton-item">
              <div class="skeleton-avatar small"></div>
              <div class="skeleton-line medium"></div>
            </div>
          </div>
          <div v-else-if="inviteSearchError" class="empty-hint">{{ inviteSearchError }}</div>
          <div v-else-if="filteredAvailableContacts.length === 0" class="empty-hint">{{ t('noContactsInvite') }}</div>
          <div
              v-else-if="inviteSearch.trim() && inviteSearchPaginationTouched && !inviteSearchHasMore"
              class="subtle-end-hint"
          >
            {{ t('noMoreResults') }}
          </div>

          <div v-if="inviteVisible && (scrollUi.invite.showBackToTop || scrollUi.invite.reachedEnd)" class="list-floating-actions picker-list-actions">
            <div v-if="scrollUi.invite.reachedEnd" class="scroll-end-pill">{{ t('reachedEnd') }}</div>
            <button
                v-if="scrollUi.invite.showBackToTop"
                type="button"
                class="scroll-top-btn"
                @click="scrollListToTop('invite')"
            >
              {{ t('backToTop') }}
            </button>
          </div>
        </div>
        <div class="dialog-footer-actions">
          <button class="tg-btn ghost" @click="inviteVisible = false">{{ t('cancel') }}</button>
          <button class="tg-btn primary" @click="submitInvite">{{ t('add') }}</button>
        </div>
      </div>
    </el-dialog>

  </div>
</template>

<script setup>
import {computed, nextTick, onMounted, onUnmounted, reactive, ref, watch} from 'vue';
import axios from 'axios';
import {ElImageViewer, ElMessage, ElMessageBox} from 'element-plus';
import {useRouter} from 'vue-router';
import 'cropperjs/dist/cropper.css';
import Cropper from 'cropperjs';

import {applyAuthResponse, ensureAccessToken, getAccessToken, getAccessPayload, logoutSession} from '../utils/auth';
import {
  buildEncryptedAttachmentDescriptor,
  decryptAttachmentCiphertext,
  encryptAttachmentFile,
  parseEncryptedAttachmentDescriptor,
} from '../utils/e2ee/attachment';
import {
  buildSenderKeyDistributionPayload,
  createGroupSenderKeyState,
  decryptGroupSenderKeyMessage,
  encryptGroupSenderKeyMessage,
  loadGroupSenderKey,
  parseSenderKeyDistributionPayload,
  saveReceivedGroupSenderKeyState,
} from '../utils/e2ee/group';
import {
  buildPrivatePreviewText,
  getGroupPreviewEntry,
  getGroupPreviewMap,
  getPrivatePreviewEntry,
  removeGroupPreviewEntry,
  removePrivatePreviewEntry,
  replaceGroupPreviewMap,
  saveGroupPreviewEntry,
  savePrivatePreviewEntry,
} from '../utils/e2ee/inbox';
import {buildBootstrapPayload, buildPrekeyRefreshPayload, generateDeviceState} from '../utils/e2ee/keys';
import {
  attachLocalIdentityToSession,
  createInitiatorSession,
  decryptEnvelopeForHistory,
  decryptIncomingEnvelope,
  deriveCacheEncryptionKey,
  encryptLocalEnvelope,
  encryptOutgoingMessage,
  listDeviceSessions,
  loadDeviceSession,
} from '../utils/e2ee/session';
import {
  clearCachedPlaintexts,
  clearGroupSenderKeyStates,
  clearOutboxMessages,
  clearStoredDeviceState,
  clearStoredSessionState,
  clearStoredSessionStates,
  listOutboxMessages,
  loadCachedPlaintextBatch,
  loadOutboxMessage,
  loadStoredDeviceState,
  removeCachedPlaintext,
  removeOutboxMessage,
  saveCachedPlaintext,
  saveCachedPlaintextBatch,
  saveOutboxMessage,
  saveStoredDeviceState,
} from '../utils/e2ee/storage';
import {API_ORIGIN, WS_ORIGIN} from '../utils/runtime';

const router = useRouter();
const messagesRef = ref(null);
const contactListRef = ref(null);
const createGroupListRef = ref(null);
const inviteListRef = ref(null);
const scrollUi = reactive({
  main: {showBackToTop: false, reachedEnd: false},
  create: {showBackToTop: false, reachedEnd: false},
  invite: {showBackToTop: false, reachedEnd: false}
});

const savedLang = localStorage.getItem('app_lang');
const currentLang = ref(savedLang || 'en');

// 后端错误文案映射。
const backendErrorTranslations = {
  '只有群主可以解散群组': 'Only the owner can disband the group',
  '只有群主可以邀请成员': 'Only the owner can invite members',
  '只有群主可以移除成员': 'Only the owner can remove members',
  '只有群主可以修改群名': 'Only the owner can rename the group',
  '只有群主可以修改群头像': 'Only the group owner can change the group avatar',
  '文件无效或已失效': 'The file is invalid or has expired',
  '文件过大': 'The file is too large',
  '不支持的文件类型': 'Unsupported file type',
  '文件名无效': 'Invalid file name',
  '文件为空': 'The file is empty',
  '文件 MIME 类型不匹配': 'The uploaded file MIME type does not match the extension',
  '文件内容与扩展名不匹配': 'The uploaded file content does not match the extension',
  '文件解密失败': 'Failed to decrypt the file',
  '无权查看该群组': 'You do not have access to this group',
  '无权向该群组发送消息': 'You do not have permission to send messages to this group',
  '群主不能移除自己': 'Owner cannot remove themselves',
  '无法撤回他人的消息': 'Cannot recall messages from others',
  '消息不存在': 'Message does not exist',
  '消息已撤回': 'Message has already been recalled',
  '当前消息不支持撤回': 'This message cannot be recalled',
  '不能向自己发送好友请求': 'You cannot send a friend request to yourself',
  '目标用户不存在': 'Target user does not exist',
  '你们已经是好友': 'You are already friends',
  '已有待处理的好友请求': 'There is already a pending friend request',
  '好友请求不存在': 'Friend request does not exist',
  '无权处理该好友请求': 'You are not allowed to handle this friend request',
  '该好友请求已处理': 'This friend request has already been handled',
  '好友关系已存在': 'Friendship already exists',
  '好友关系不存在': 'Friendship does not exist',
  '当前仅支持好友发起新私聊': 'Only friends can start a new private chat right now',
  '当前无权发送私聊消息': 'You can no longer send messages in this private chat',
  '只能邀请好友建群': 'Only friends can be invited when creating a group',
  '只能邀请好友入群': 'Only friends can be invited into the group',
  '该用户已在群组中': 'This user is already in the group',
  '该用户已有待处理群邀请': 'This user already has a pending group invite',
  '该用户已有待处理入群申请': 'This user already has a pending join request',
  '群邀请不存在': 'Group invite does not exist',
  '无权处理该群邀请': 'You are not allowed to handle this group invite',
  '该群邀请已处理': 'This group invite has already been handled',
  '你已有待处理的入群申请': 'You already have a pending join request',
  '你已收到该群组邀请': 'You already have a pending invite for this group',
  '入群申请不存在': 'Join request does not exist',
  '只有群主可以查看入群申请': 'Only the group owner can view join requests',
  '只有群主可以处理入群申请': 'Only the group owner can handle join requests',
  '该入群申请已处理': 'This join request has already been handled',
  '只有群主可以发送群邀请': 'Only the group owner can send group invites',
  '只有群主可以取消群邀请': 'Only the group owner can cancel group invites',
  '群组不存在': 'Group does not exist',
  '群头像上传失败': 'Failed to upload group avatar',
  '会话已失效，请重新登录': 'Session expired, please login again',
  '刷新会话不存在': 'Refresh session not found',
  '当前会话尚未绑定设备': 'Current session is not bound to a device yet',
  '设备已被撤销': 'This device has been revoked',
  '设备不存在': 'Device does not exist',
  '无权更新该设备的 prekeys': 'You are not allowed to update prekeys for this device',
  '当前无权获取该用户的 prekey bundle': 'You are not allowed to fetch this user\'s prekey bundle',
  '目标设备不存在': 'Target device does not exist',
  'E2EE 消息缺少设备 envelope': 'The E2EE message is missing device envelopes',
  '消息已发送': 'This message was already sent',
  'E2EE 会话不存在': 'The E2EE conversation does not exist',
  '消息投递状态不存在': 'The message delivery state does not exist',
  '无效的消息确认状态': 'Invalid message acknowledgement status',
  '目标用户设备尚未准备好建立 E2EE 会话': 'The target user has no device ready for an E2EE session',
  '消息格式无效': 'Invalid message format',
  'E2EE 消息存在非法接收设备': 'The E2EE message contains an invalid recipient device',
  '附件不存在': 'Attachment does not exist',
  '无权上传该附件': 'You are not allowed to upload this attachment',
  '附件上传状态无效': 'The attachment upload state is invalid',
  '附件上传已过期': 'The attachment upload has expired',
  '附件大小不匹配': 'The attachment size does not match',
  '附件哈希无效': 'The attachment hash is invalid',
  '附件内容不存在': 'The attachment content does not exist',
  '附件哈希校验失败': 'The attachment hash verification failed',
  '无权绑定该附件': 'You are not allowed to link this attachment',
  '附件尚未完成上传': 'The attachment upload is not complete',
  '附件已绑定消息': 'The attachment is already linked to a message',
  '无权访问该附件': 'You are not allowed to access this attachment',
};

const translateError = (msg) => {
  if (currentLang.value === 'en' && backendErrorTranslations[msg]) return backendErrorTranslations[msg];
  return msg;
};

const translations = {
  en: {
    search: 'Search...',
    me: 'Me',
    noMessage: 'No messages',
    online: 'online',
    offline: 'offline',
    inputPlaceholder: 'Write a message...',
    send: 'Send',
    emptyState: 'Select a contact to start messaging',
    youPrefix: 'You:',
    switchLangTip: 'Switch to Chinese',
    sendFileTip: 'Send File',
    readBy: 'Read by',
    settings: 'Settings',
    logout: 'Log Out',
    logoutConfirmTitle: 'Confirm Logout',
    logoutConfirmMessage: 'Are you sure you want to log out of this account?',
    logoutConfirmAction: 'Log Out',
    profile: 'Profile',
    security: 'Security',
    oldPassword: 'Old Password',
    newPassword: 'New Password',
    newUsernamePlaceholder: 'New Username',
    save: 'Save',
    changePassword: 'Change Password',
    usernameUpdated: 'Username updated',
    passwordUpdated: 'Password changed',
    groupCreated: 'Group created',
    groupUpdated: 'Group updated',
    createGroup: 'Create Group',
    groupNamePlaceholder: 'Group Name',
    cancel: 'Cancel',
    create: 'Create',
    username: 'Username',
    selectMembers: 'Invite Friends',
    selectMembersRequired: 'Please select at least one friend',
    clickToManage: 'Click to info',
    manageGroup: 'Group Info',
    groupName: 'Group Name',
    disbandGroup: 'Disband Group',
    confirmDisband: 'Are you sure you want to disband this group?',
    disbandSuccess: 'Group disbanded successfully',
    members: 'Members',
    owner: 'Owner',
    add: 'Add',
    removeMember: 'Remove Member',
    inviteMembers: 'Invite Members',
    noContactsInvite: 'No contacts available to invite',
    confirmRemoveMember: 'Are you sure you want to remove this member?',
    removeMemberSuccess: 'Member removed successfully',
    inviteSuccess: 'Members invited successfully',
    chats: 'Chats',
    users: 'Users',
    groups: 'Groups',
    searchEmpty: 'No matching users or groups',
    searchLoading: 'Searching...',
    sidebarEmpty: 'No conversations yet. Search for a user or group to get started.',
    startChat: 'Start chat',
    groupInviteOnly: 'This group is invite-only for now',
    joined: 'Joined',
    notJoined: 'Not joined',
    membersCount: 'members',
    connectionNotReady: 'Connection is not ready yet. Please try again.',
    draftChat: 'New chat',
    draftPrefix: 'Draft:',
    openJoinedGroup: 'Open joined group',
    searchUsersForGroup: 'Search friends to invite',
    createGroupSearchEmpty: 'No matching friends found',
    searchInviteMembers: 'Search members to invite',
    groupUnavailable: 'You no longer have access to this group',
    closeDraftChat: 'Close new chat',
    searchRateLimited: 'Too many searches. Please wait a moment and try again.',
    searchFailed: 'Search failed. Please try again.',
    loadMore: 'Load more',
    loadingMore: 'Loading...',
    noMoreResults: 'No more results',
    backToTop: 'Back to top',
    reachedEnd: 'Reached the end',
    notifications: 'Notifications',
    friendRequests: 'Friend Requests',
    friendsHub: 'Friends',
    incomingRequests: 'Incoming',
    outgoingRequests: 'Outgoing',
    friendsList: 'Friends',
    noIncomingRequests: 'No incoming requests',
    noOutgoingRequests: 'No outgoing requests',
    noFriendsYet: 'No friends yet',
    addFriend: 'Add friend',
    friend: 'Friend',
    accept: 'Accept',
    reject: 'Reject',
    cancelRequest: 'Cancel request',
    removeFriendAction: 'Remove friend',
    friendRequestSent: 'Friend request sent',
    friendRequestAccepted: 'Friend request accepted',
    friendRequestRejected: 'Friend request rejected',
    friendRequestCancelled: 'Friend request cancelled',
    friendRemoved: 'Friend removed',
    addFriendToChat: 'Add as a friend to start chatting',
    privateChatLocked: 'Friend required to continue chatting',
    groupRequests: 'Group Access',
    receivedInvites: 'Invites',
    myJoinRequests: 'My Requests',
    ownedJoinRequests: 'Owned Groups',
    pendingJoinRequests: 'Join Requests',
    sentInvites: 'Sent Invites',
    noGroupInvites: 'No group invites',
    noJoinRequests: 'No join requests',
    noPendingGroupRequests: 'No pending requests for this group',
    noPendingInvites: 'No pending invites for this group',
    applyToJoin: 'Apply to join',
    joinRequestSent: 'Join request sent',
    joinRequestCancelled: 'Join request cancelled',
    groupInviteAccepted: 'Group invite accepted',
    groupInviteRejected: 'Group invite rejected',
    groupInviteCancelled: 'Group invite cancelled',
    groupInviteCreated: 'Group invite created',
    groupJoinApproved: 'Join request approved',
    groupJoinRejected: 'Join request rejected',
    groupCreatedAvatarFailed: 'Group created, but avatar upload failed',
    invited: 'Invited',
    requested: 'Requested',
    requestToJoin: 'Request to join',
    openRequests: 'Requests',
    acceptInviteHint: 'Use the invite actions to accept or reject this group invite',
    joinRequestPendingHint: 'Your join request is pending review',
    cancelInviteAction: 'Cancel invite',
    chatUnavailable: 'This chat is not ready yet. Please try again in a moment.',
    recallMessage: 'Recall',
    confirmRecallMessage: 'Recall this message for everyone?',
    messageRecalledSelf: 'You recalled a message',
    messageRecalledOther: 'This message was recalled',
    recalledPreview: '[Message recalled]',
    messageQueued: 'Message queued and will send when the connection recovers',
    queued: 'Queued',
    sending: 'Sending',
    sent: 'Sent',
    delivered: 'Delivered',
    read: 'Read',
    failed: 'Failed',
    retry: 'Retry',
    imageLoading: 'Loading image…',
    imageLoadFailed: 'Image failed to load'
  },
  zh: {
    search: '搜索用户或群组',
    me: '我',
    noMessage: '无消息',
    online: '在线',
    offline: '离线',
    inputPlaceholder: '请输入消息...',
    send: '发送',
    emptyState: '请选择一个联系人开始加密聊天',
    youPrefix: '你:',
    switchLangTip: '切换为英文',
    sendFileTip: '发送文件',
    readBy: '已读人员',
    settings: '设置',
    logout: '退出登录',
    logoutConfirmTitle: '确认退出登录',
    logoutConfirmMessage: '确定要退出当前账号吗？',
    logoutConfirmAction: '退出登录',
    profile: '个人资料',
    security: '安全',
    oldPassword: '旧密码',
    newPassword: '新密码',
    newUsernamePlaceholder: '新用户名',
    save: '保存',
    changePassword: '修改密码',
    usernameUpdated: '用户名已更新',
    passwordUpdated: '密码已修改，请重新登录',
    groupCreated: '群组已创建',
    groupUpdated: '群组已更新',
    createGroup: '创建群组',
    groupNamePlaceholder: '群组名称',
    cancel: '取消',
    create: '创建',
    username: '用户名',
    selectMembers: '邀请好友',
    selectMembersRequired: '请至少选择一位好友',
    clickToManage: '点击查看信息',
    manageGroup: '群组信息',
    groupName: '群组名称',
    disbandGroup: '解散群组',
    confirmDisband: '确定要解散该群组吗？此操作无法撤销。',
    disbandSuccess: '群组已解散',
    members: '成员',
    owner: '群主',
    add: '添加',
    removeMember: '移除成员',
    inviteMembers: '邀请成员',
    noContactsInvite: '没有可邀请的联系人',
    confirmRemoveMember: '确定要移除该成员吗？',
    removeMemberSuccess: '成员已移除',
    inviteSuccess: '成员邀请成功',
    chats: '会话',
    users: '用户',
    groups: '群组',
    searchEmpty: '未找到匹配的用户或群组',
    searchLoading: '搜索中...',
    sidebarEmpty: '还没有会话，可通过搜索用户或群组开始。',
    startChat: '发起私聊',
    groupInviteOnly: '该群组暂只支持被邀请加入',
    joined: '已加入',
    notJoined: '未加入',
    membersCount: '名成员',
    connectionNotReady: '连接尚未建立，请稍后再试',
    draftChat: '新会话',
    draftPrefix: '草稿:',
    openJoinedGroup: '打开已加入群组',
    searchUsersForGroup: '搜索要邀请的好友',
    createGroupSearchEmpty: '未找到匹配的好友',
    searchInviteMembers: '搜索要邀请的成员',
    groupUnavailable: '你已无法访问该群组',
    closeDraftChat: '关闭新会话',
    searchRateLimited: '搜索过于频繁，请稍后再试',
    searchFailed: '搜索失败，请稍后重试',
    loadMore: '加载更多',
    loadingMore: '加载中...',
    noMoreResults: '没有更多结果了',
    backToTop: '回到顶部',
    reachedEnd: '已经到底了',
    notifications: '通知中心',
    friendRequests: '好友请求',
    friendsHub: '好友',
    incomingRequests: '收到的请求',
    outgoingRequests: '发出的请求',
    friendsList: '好友列表',
    noIncomingRequests: '暂无收到的好友请求',
    noOutgoingRequests: '暂无发出的好友请求',
    noFriendsYet: '还没有好友',
    addFriend: '添加好友',
    friend: '好友',
    accept: '接受',
    reject: '拒绝',
    cancelRequest: '取消请求',
    removeFriendAction: '删除好友',
    friendRequestSent: '好友请求已发送',
    friendRequestAccepted: '好友请求已接受',
    friendRequestRejected: '好友请求已拒绝',
    friendRequestCancelled: '好友请求已取消',
    friendRemoved: '好友已删除',
    addFriendToChat: '需先成为好友才能发起私聊',
    privateChatLocked: '需恢复好友关系后才能继续发消息',
    groupRequests: '群组请求',
    receivedInvites: '收到的邀请',
    myJoinRequests: '我的申请',
    ownedJoinRequests: '我管理的群',
    pendingJoinRequests: '待处理申请',
    sentInvites: '已发邀请',
    noGroupInvites: '暂无群邀请',
    noJoinRequests: '暂无入群申请',
    noPendingGroupRequests: '当前群暂无待处理申请',
    noPendingInvites: '当前群暂无待处理邀请',
    applyToJoin: '申请加入',
    joinRequestSent: '入群申请已提交',
    joinRequestCancelled: '入群申请已取消',
    groupInviteAccepted: '群邀请已接受',
    groupInviteRejected: '群邀请已拒绝',
    groupInviteCancelled: '群邀请已取消',
    groupInviteCreated: '群邀请已创建',
    groupJoinApproved: '入群申请已批准',
    groupJoinRejected: '入群申请已拒绝',
    groupCreatedAvatarFailed: '群组已创建，但头像上传失败',
    invited: '已邀请',
    requested: '已申请',
    requestToJoin: '申请加入群组',
    openRequests: '查看申请',
    acceptInviteHint: '请使用邀请操作接受或拒绝该群邀请',
    joinRequestPendingHint: '你的入群申请正在等待处理',
    cancelInviteAction: '取消邀请',
    chatUnavailable: '当前会话暂不可用，请稍后再试。',
    recallMessage: '撤回',
    confirmRecallMessage: '确定撤回这条消息吗？',
    messageRecalledSelf: '你撤回了一条消息',
    messageRecalledOther: '该消息已被撤回',
    recalledPreview: '[消息已撤回]',
    messageQueued: '消息已进入队列，连接恢复后会自动发送',
    queued: '排队中',
    sending: '发送中',
    sent: '已发送',
    delivered: '已送达',
    read: '已读',
    failed: '发送失败',
    retry: '重发',
    imageLoading: '图片加载中…',
    imageLoadFailed: '图片加载失败'
  }
};

const t = (key) => translations[currentLang.value][key];

const toggleLanguage = () => {
  currentLang.value = currentLang.value === 'en' ? 'zh' : 'en';
  localStorage.setItem('app_lang', currentLang.value);
};

const formatLastMessage = (msg) => {
  if (!msg) return t('noMessage');
  let formatted = msg;
  if (formatted.startsWith('You: ')) {
    formatted = formatted.replace('You:', t('youPrefix'));
  }
  return formatted.replace(/\[(?:Message recalled|消息已撤回)\]/g, t('recalledPreview'));
};

const normalizePreviewText = (text) => {
  return text.replace(/\s+/g, ' ').trim();
};

const isMessageRecalled = (message) => {
  return message?.isRecalled === true || message?.is_recalled === true;
};

const buildConversationRecallPreview = ({chatType, senderName = '', isOwnMessage = false}) => {
  if (isOwnMessage) {
    return `You: ${t('recalledPreview')}`;
  }
  if (chatType === 'group') {
    return `${senderName || 'Unknown'}: ${t('recalledPreview')}`;
  }
  return t('recalledPreview');
};

const getRecalledMessageText = (message) => {
  return message?.from === myUserId ? t('messageRecalledSelf') : t('messageRecalledOther');
};

// 图片预览。
const showViewer = ref(false);
const previewUrl = ref('');
const attachmentObjectUrls = reactive({});
const attachmentLoadErrors = reactive({});
const attachmentLoadPromises = new Map();

const previewImage = async (content) => {
  previewUrl.value = await resolveAttachmentUrl(content);
  if (!previewUrl.value) return;
  showViewer.value = true;
};
const closeViewer = () => {
  showViewer.value = false;
};

// 会话与输入状态。
const contactList = ref([]);
const messages = ref([]);
const inputText = ref('');
const searchText = ref('');
const allUsers = ref([]);
const searchResults = reactive({
  users: [],
  groups: [],
  loading: false,
  error: '',
  usersHasMore: false,
  groupsHasMore: false,
  usersNextOffset: 0,
  groupsNextOffset: 0,
  groupsAnchorTs: null,
  usersPaginationTouched: false,
  groupsPaginationTouched: false,
  usersLoadingMore: false,
  groupsLoadingMore: false
});
const currentChatId = ref(null);
const currentChatType = ref('private');
let socket = null;
let searchTimer = null;
let latestSearchId = 0;
let searchAbortController = null;
let userLoadMoreAbortController = null;
let groupLoadMoreAbortController = null;
const sessionFeatureFlags = reactive({
  e2ee_private_enabled: false,
  e2ee_group_enabled: false
});

const createGroupVisible = ref(false);
const newGroupName = ref('');
const selectedMembers = ref([]);
const createGroupMemberSearch = ref('');
const createGroupSearchResults = ref([]);
const createGroupSearchLoading = ref(false);
const createGroupSearchError = ref('');
const createGroupSearchHasMore = ref(false);
const createGroupSearchNextOffset = ref(0);
const createGroupSearchPaginationTouched = ref(false);
const createGroupSearchLoadingMore = ref(false);
let createGroupSearchRequestId = 0;
let createGroupSearchTimer = null;
let createGroupSearchAbortController = null;

// 群组管理状态。
const groupManageVisible = ref(false);
const editingGroupName = ref('');
const currentGroupAvatar = ref('');
const groupMembers = ref([]);
const isGroupOwner = ref(false);
const notificationCenterVisible = ref(false);
const notificationCenterTab = ref('friends');
const groupAccessTab = ref('invites');
const groupAccessLoading = ref(false);
const groupAccessError = ref('');
const receivedGroupInvites = ref([]);
const myGroupJoinRequests = ref([]);
const ownedGroupJoinRequests = ref([]);
const currentGroupInvites = ref([]);
const inviteVisible = ref(false);
const inviteSelection = ref([]);
const inviteSearch = ref('');
const inviteSearchResults = ref([]);
const inviteSearchLoading = ref(false);
const inviteAccessLoading = ref(false);
const inviteSearchError = ref('');
const inviteSearchHasMore = ref(false);
const inviteSearchNextOffset = ref(0);
const inviteSearchPaginationTouched = ref(false);
const inviteSearchLoadingMore = ref(false);
let inviteSearchRequestId = 0;
let inviteSearchTimer = null;
let inviteSearchAbortController = null;
let inviteAccessRequestId = 0;
let inviteAccessAbortController = null;
const deliveryStatusCache = reactive({});
const messageReceiptCache = reactive({});
const readReceiptPopover = reactive({ visible: false, x: 0, y: 0, readers: [] });
const pendingGroupPreviewHydrations = new Set();
let startupInitialized = false;
let outboxFlushInProgress = false;
let socketReconnectTimer = null;
let socketReconnectAttempts = 0;
let socketConnectPromise = null;
let chatViewUnmounted = false;

const friendRequestsTab = ref('incoming');
const friendRequestsLoading = ref(false);
const incomingFriendRequests = ref([]);
const outgoingFriendRequests = ref([]);
const friendsList = ref([]);
const friendActionTarget = ref('');

let token = getAccessToken();
const myUsername = ref(localStorage.getItem('username') || '');
let myUserId = 0;
const myUserIdState = ref(0);
const currentDeviceId = ref('');
const currentDeviceState = ref(null);
const deviceRevocationInProgress = ref(false);
const groupDeviceDirectory = reactive({});

const syncIdentityFromAccessToken = () => {
  token = getAccessToken();
  const payload = getAccessPayload();
  if (payload?.user_id !== undefined && payload?.user_id !== null) {
    myUserId = Number(payload.user_id || 0);
    myUserIdState.value = myUserId;
  }
  currentDeviceId.value = payload?.device_id || currentDeviceId.value || '';
};

syncIdentityFromAccessToken();

const API_BASE = `${API_ORIGIN}/api`;
const getDraftStorageKey = () => `chat_drafts_${myUserId || 'guest'}`;

const myAvatar = ref(localStorage.getItem('avatar') || '');
const pendingAvatarBlob = ref(null);
const pendingAvatarUrl = ref('');
const pendingGroupAvatarBlob = ref(null);
const pendingGroupAvatarUrl = ref('');

const getAvatarUrl = (filename) => {
  if (!filename) return '';
  return `${API_BASE}/user/avatar/${filename}`;
};

const getGroupAvatarUrl = (filename) => {
  if (!filename) return '';
  return `${API_BASE}/chat/group/avatar/${filename}`;
};

const getConversationAvatarUrl = (contact) => {
  if (!contact?.avatar) return '';
  return contact.type === 'group' ? getGroupAvatarUrl(contact.avatar) : getAvatarUrl(contact.avatar);
};

const getAvatarUploadFilename = (blob, baseName) => {
  if (blob?.type === 'image/gif') return `${baseName}.gif`;
  if (blob?.type === 'image/jpeg') return `${baseName}.jpg`;
  return `${baseName}.png`;
};

const isGroupAvatarTarget = (target = avatarUploadTarget.value) => {
  return target === 'group' || target === 'create-group';
};

// 头像上传与裁剪
const avatarInputRef = ref(null);
const createGroupAvatarInputRef = ref(null);
const groupAvatarInputRef = ref(null);
const cropperDialogVisible = ref(false);
const currentCropImageUrl = ref('');
const cropperImgRef = ref(null);
let cropperInstance = null;
const isCropping = ref(false);
const avatarUploadTarget = ref('profile');

const getPendingAvatarBlobRef = () => {
  return isGroupAvatarTarget() ? pendingGroupAvatarBlob : pendingAvatarBlob;
};

const getPendingAvatarUrlRef = () => {
  return isGroupAvatarTarget() ? pendingGroupAvatarUrl : pendingAvatarUrl;
};

const clearPendingAvatarSelection = (target = avatarUploadTarget.value) => {
  const blobRef = isGroupAvatarTarget(target) ? pendingGroupAvatarBlob : pendingAvatarBlob;
  const urlRef = isGroupAvatarTarget(target) ? pendingGroupAvatarUrl : pendingAvatarUrl;
  blobRef.value = null;
  if (urlRef.value) URL.revokeObjectURL(urlRef.value);
  urlRef.value = '';
};

const setPendingAvatarSelection = (blob) => {
  const blobRef = getPendingAvatarBlobRef();
  const urlRef = getPendingAvatarUrlRef();
  blobRef.value = blob;
  if (urlRef.value) URL.revokeObjectURL(urlRef.value);
  urlRef.value = URL.createObjectURL(blob);
};

const triggerAvatarUpload = (target = 'profile') => {
  avatarUploadTarget.value = target;
  const inputRef = target === 'group'
    ? groupAvatarInputRef
    : target === 'create-group'
      ? createGroupAvatarInputRef
      : avatarInputRef;
  if (inputRef.value) {
    inputRef.value.click();
  }
};

const handleAvatarChange = (e) => {
  const file = e.target.files[0];
  if (!file) return;
  e.target.value = ''; 
  
  if (file.type === 'image/gif') {
    setPendingAvatarSelection(file);
    return;
  }

  if (currentCropImageUrl.value) {
    URL.revokeObjectURL(currentCropImageUrl.value);
  }
  const url = URL.createObjectURL(file);
  currentCropImageUrl.value = url;
  cropperDialogVisible.value = true;
  
  nextTick(() => {
    if (cropperImgRef.value) {
      if (cropperInstance) cropperInstance.destroy();
      cropperInstance = new Cropper(cropperImgRef.value, {
        aspectRatio: 1,
        viewMode: 1,
        dragMode: 'move',
        autoCropArea: 1,
        cropBoxMovable: false,
        cropBoxResizable: false,
        toggleDragModeOnDblclick: false,
      });
    }
  });
};

const cancelCrop = () => {
  cropperDialogVisible.value = false;
  if (cropperInstance) {
    cropperInstance.destroy();
    cropperInstance = null;
  }
  if (currentCropImageUrl.value) {
    URL.revokeObjectURL(currentCropImageUrl.value);
    currentCropImageUrl.value = '';
  }
};

const confirmAvatarCrop = () => {
  if (!cropperInstance) return;
  isCropping.value = true;
  cropperInstance.getCroppedCanvas({
    width: 256,
    height: 256,
  }).toBlob((blob) => {
    isCropping.value = false;
    if (!blob) return;
    
    setPendingAvatarSelection(blob);
    
    cropperDialogVisible.value = false;
    if (cropperInstance) {
      cropperInstance.destroy();
      cropperInstance = null;
    }
    if (currentCropImageUrl.value) {
      URL.revokeObjectURL(currentCropImageUrl.value);
      currentCropImageUrl.value = '';
    }
  }, 'image/png');
};

const loadConversationDrafts = () => {
  try {
    const raw = localStorage.getItem(getDraftStorageKey());
    if (!raw) return {};

    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (e) {
    console.error(e);
    return {};
  }
};

const conversationDrafts = ref(loadConversationDrafts());

const getConversationKey = (id, type) => `${type}:${id}`;
const CHINA_TZ = 'Asia/Shanghai';
const CLOCK_FORMATTER = new Intl.DateTimeFormat('zh-CN', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: CHINA_TZ,
});
const GROUP_SENDER_THEMES = [
  {text: '#d84a45', tint: 'rgba(216, 74, 69, 0.18)'},
  {text: '#1d76d3', tint: 'rgba(29, 118, 211, 0.18)'},
  {text: '#0f9f74', tint: 'rgba(15, 159, 116, 0.18)'},
  {text: '#9655d6', tint: 'rgba(150, 85, 214, 0.18)'},
  {text: '#de7b18', tint: 'rgba(222, 123, 24, 0.18)'},
  {text: '#cd4d86', tint: 'rgba(205, 77, 134, 0.18)'},
];

const parseDisplayTimestamp = (value) => {
  if (value === null || value === undefined || value === '') return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === 'number') {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  if (typeof value === 'string') {
    const normalized = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value)
      ? `${value}Z`
      : value;
    const date = new Date(normalized);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  return null;
};

const formatClockTime = (timestamp) => {
  const date = parseDisplayTimestamp(timestamp);
  return date ? CLOCK_FORMATTER.format(date) : '';
};

const formatSidebarTime = (timestamp) => formatClockTime(timestamp);

const hashGroupSenderSeed = (value) => {
  let hash = 0;
  const text = String(value || 'group-sender');
  for (let index = 0; index < text.length; index += 1) {
    hash = ((hash << 5) - hash) + text.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash);
};

const isIncomingGroupMessage = (msg) => currentChatType.value === 'group' && msg.from !== myUserId;

const isImageMessage = (msg) => getMsgType(msg) === 'image';

const shouldShowGroupBubbleHeader = (msg) => isIncomingGroupMessage(msg);

const getGroupSenderTheme = (msg) => {
  const seed = `${msg.username || ''}:${msg.from || 0}`;
  return GROUP_SENDER_THEMES[hashGroupSenderSeed(seed) % GROUP_SENDER_THEMES.length];
};

const getGroupSenderNameStyle = (msg) => ({
  color: getGroupSenderTheme(msg).text,
});

const getMessageTimeLabel = (msg) => {
  const rawTimestamp = msg.timestamp || msg.created_at || null;
  return formatClockTime(rawTimestamp);
};

const formatLastSeenLabel = (timestamp) => {
  const date = parseDisplayTimestamp(timestamp);
  if (!date) {
    return '-';
  }
  return `${date.toLocaleDateString(currentLang.value === 'en' ? 'en-CA' : 'zh-CN')} ${formatClockTime(date)}`;
};

const normalizeReceiptSummary = (summary, fallbackStatus = 'sent') => {
  const readBy = Array.isArray(summary?.read_by) ? summary.read_by : [];
  return {
    status: summary?.status || fallbackStatus,
    deliveredUserCount: Number(summary?.delivered_user_count || 0),
    readUserCount: Number(summary?.read_user_count || 0),
    readBy,
  };
};

const cacheReceiptSummary = (messageId, summary, fallbackStatus = 'sent') => {
  if (!messageId || !summary) {
    return normalizeReceiptSummary(null, fallbackStatus);
  }
  const normalized = normalizeReceiptSummary(summary, fallbackStatus);
  deliveryStatusCache[messageId] = normalized.status;
  messageReceiptCache[messageId] = normalized;
  return normalized;
};

const getMessageReceiptSummary = (msg) => {
  const cached = msg?.id ? messageReceiptCache[msg.id] : null;
  if (cached) {
    return cached;
  }
  return normalizeReceiptSummary(msg?.receiptSummary, msg?.deliveryStatus || 'sent');
};

const getAcceptedOwnDeliveryStatus = (messageId) => {
  const cachedStatus = messageId ? deliveryStatusCache[messageId] : null;
  if (cachedStatus === 'read' || cachedStatus === 'delivered' || cachedStatus === 'failed') {
    return cachedStatus;
  }
  return 'sent';
};

const getGroupReadSummaryText = (msg) => {
  const receiptSummary = getMessageReceiptSummary(msg);
  if (!receiptSummary.readBy.length) {
    return '';
  }
  const names = receiptSummary.readBy.map((entry) => entry.username).filter(Boolean);
  const separator = currentLang.value === 'en' ? ', ' : '、';
  if (!names.length) {
    return t('read');
  }
  if (names.length === 1) {
    return `${names[0]} ${t('read')}`;
  }
  if (names.length === 2) {
    return `${names[0]}${separator}${names[1]} ${t('read')}`;
  }
  return `${names[0]}${separator}${names[1]} +${names.length - 2} ${t('read')}`;
};

const getGroupReadSummaryTitle = (msg) => {
  const receiptSummary = getMessageReceiptSummary(msg);
  if (!receiptSummary.readBy.length) {
    return '';
  }
  return receiptSummary.readBy.map((entry) => {
    return entry.read_at ? `${entry.username} · ${formatLastSeenLabel(entry.read_at)}` : entry.username;
  }).join('\n');
};

const getGroupReadReaders = (msg) => {
  const receiptSummary = getMessageReceiptSummary(msg);
  return receiptSummary.readBy.map((entry) => {
    const initials = (entry.username || 'U').charAt(0).toUpperCase();
    return {
      userId: entry.user_id,
      username: entry.username,
      initials,
      avatar: entry.avatar ? getAvatarUrl(entry.avatar) : '',
      color: getAvatarColor(entry.user_id),
      readAt: entry.read_at,
    };
  });
};

const openReadReceiptPopover = (event, msg) => {
  const readers = getGroupReadReaders(msg);
  if (!readers.length) return;
  const rect = event.target.getBoundingClientRect();
  let x = rect.left;
  let y = rect.bottom + 4;
  const popoverWidth = 260;
  const popoverHeight = Math.min(300, 40 + readers.length * 50);
  if (x + popoverWidth > window.innerWidth - 10) {
    x = window.innerWidth - popoverWidth - 10;
  }
  if (x < 10) x = 10;
  if (y + popoverHeight > window.innerHeight - 10) {
    y = rect.top - popoverHeight - 4;
  }
  if (y < 10) y = 10;
  readReceiptPopover.visible = true;
  readReceiptPopover.x = x;
  readReceiptPopover.y = y;
  readReceiptPopover.readers = readers;
};

const closeReadReceiptPopover = () => {
  readReceiptPopover.visible = false;
};

const getDeliveryStatusLabel = (msg) => {
  const receiptSummary = getMessageReceiptSummary(msg);
  if (currentChatType.value === 'group' && msg?.from === myUserId && receiptSummary.readBy.length) {
    return getGroupReadSummaryText(msg);
  }

  const statusValue = receiptSummary.status || msg.deliveryStatus || 'sent';
  if (statusValue === 'queued') return t('queued');
  if (statusValue === 'pending') return t('sending');
  if (statusValue === 'delivered') return t('delivered');
  if (statusValue === 'read') return t('read');
  if (statusValue === 'failed') return t('failed');
  return t('sent');
};

const normalizeDraftEntry = (entry) => {
  if (!entry) return {text: ''};
  if (typeof entry === 'string') {
    return {text: entry, updatedAt: 0};
  }

  return {
    text: entry.text || '',
    username: entry.username || '',
    updatedAt: entry.updatedAt || 0,
    type: entry.type || '',
    canChat: entry.canChat
  };
};

const persistConversationDrafts = () => {
  try {
    localStorage.setItem(getDraftStorageKey(), JSON.stringify(conversationDrafts.value));
  } catch (e) {
    console.error(e);
  }
};

const getDraftForConversation = (id, type) => {
  if (id === null || !type) return '';
  return normalizeDraftEntry(conversationDrafts.value[getConversationKey(id, type)]).text;
};

const getDraftMetaForConversation = (id, type) => {
  if (id === null || !type) return {text: '', updatedAt: 0, username: ''};
  return normalizeDraftEntry(conversationDrafts.value[getConversationKey(id, type)]);
};

const getDraftPreviewForConversation = (id, type) => {
  const draftText = getDraftForConversation(id, type);
  if (!draftText) return '';
  return `${t('draftPrefix')} ${normalizePreviewText(draftText)}`;
};

const setDraftForConversation = (id, type, text, meta = {}) => {
  if (id === null || !type) return;

  const key = getConversationKey(id, type);
  if (text) {
    conversationDrafts.value = {
      ...conversationDrafts.value,
      [key]: {
        text,
        username: meta.username || '',
        updatedAt: Date.now(),
        type,
        canChat: meta.canChat
      }
    };
  } else if (key in conversationDrafts.value) {
    const nextDrafts = {...conversationDrafts.value};
    delete nextDrafts[key];
    conversationDrafts.value = nextDrafts;
  }

  persistConversationDrafts();
};

const clearDraftForConversation = (id, type) => {
  setDraftForConversation(id, type, '');
};

const currentChatUser = computed(() => {
  return contactList.value.find(u => {
    return u.id === currentChatId.value && u.type === currentChatType.value;
  });
});

const currentChatCanSend = computed(() => {
  if (!currentChatUser.value) return false;
  if (currentChatType.value === 'private') {
    return currentChatUser.value.canChat !== false && sessionFeatureFlags.e2ee_private_enabled && Boolean(currentDeviceState.value);
  }
  if (currentChatType.value === 'group') {
    return sessionFeatureFlags.e2ee_group_enabled && Boolean(currentDeviceState.value) && Boolean(currentChatUser.value.e2eeConversationId);
  }
  return false;
});

const incomingFriendRequestCount = computed(() => incomingFriendRequests.value.length);
const groupAccessBadgeCount = computed(() => {
  return receivedGroupInvites.value.length + myGroupJoinRequests.value.length + ownedGroupJoinRequests.value.length;
});
const notificationBadgeCount = computed(() => incomingFriendRequestCount.value + groupAccessBadgeCount.value);

const buildFriendActionKey = (userId) => `friend:${userId}`;
const buildGroupActionKey = (groupId) => `group:${groupId}`;

const isActionLoading = (key) => friendActionTarget.value === key;
const isFriendActionLoading = (userId) => isActionLoading(buildFriendActionKey(userId));
const isGroupActionLoading = (groupId) => isActionLoading(buildGroupActionKey(groupId));

const updateUserRelationshipInCollections = (userId, relationshipStatus, requestId = null, canStartChat = null) => {
  const patch = (user) => {
    if (user.id !== userId) return user;
    return {
      ...user,
      relationship_status: relationshipStatus,
      friend_request_id: requestId,
      can_start_chat: canStartChat === null ? (user.has_conversation || relationshipStatus === 'friend') : canStartChat
    };
  };

  searchResults.users = searchResults.users.map(patch);
  createGroupSearchResults.value = createGroupSearchResults.value.map(patch);
  inviteSearchResults.value = inviteSearchResults.value.map(patch);
};

const getSearchUserState = (userId) => {
  return searchResults.users.find(user => user.id === userId) || null;
};

const updateGroupAccessStateInSearch = (groupId, patch) => {
  searchResults.groups = searchResults.groups.map(group => {
    if (group.id !== groupId) return group;
    return {...group, ...patch};
  });
};

const getConversationPreview = (contact) => {
  const draftPreview = getDraftPreviewForConversation(contact.id, contact.type);
  if (draftPreview) return draftPreview;
  if (contact.type === 'private' && contact.canChat === false) return t('privateChatLocked');
  return formatLastMessage(contact.lastMessage);
};

const getConversationTimeLabel = (contact) => {
  const draftMeta = getDraftMetaForConversation(contact.id, contact.type);
  if (draftMeta.text && draftMeta.updatedAt) {
    return formatSidebarTime(draftMeta.updatedAt);
  }
  return contact.lastTime || formatSidebarTime(contact.lastActivityAt);
};

const getTimestampMs = (value) => {
  const parsed = parseDisplayTimestamp(value);
  return parsed ? parsed.getTime() : 0;
};

const pickLatestTimestamp = (...values) => {
  let winner = null;
  let winnerTs = 0;
  values.forEach((value) => {
    const nextTs = getTimestampMs(value);
    if (nextTs > winnerTs) {
      winnerTs = nextTs;
      winner = parseDisplayTimestamp(value)?.toISOString() || null;
    }
  });
  return winner;
};

const getConversationPreviewTimestamp = (conversationItem) => {
  return conversationItem?.last_message_created_at || conversationItem?.last_message_at || null;
};

const getMatchedConversationContact = (contact, conversationId) => {
  if (!contact || !conversationId) {
    return null;
  }
  return Number(contact.e2eeConversationId) === Number(conversationId) ? contact : null;
};

const isPreviewEntryAlignedWithConversation = (previewEntry, conversationItem) => {
  if (!previewEntry?.timestamp) {
    return false;
  }
  const previewTimestamp = getConversationPreviewTimestamp(conversationItem);
  if (!previewTimestamp) {
    return false;
  }
  return getTimestampMs(previewEntry.timestamp) === getTimestampMs(previewTimestamp);
};

const getValidatedPrivatePreviewEntry = (conversationItem) => {
  const previewScope = getPreviewStorageScope();
  const previewEntry = getPrivatePreviewEntry(myUserId, conversationItem.partner_id, previewScope);
  if (!previewEntry) {
    return null;
  }
  if (isPreviewEntryAlignedWithConversation(previewEntry, conversationItem)) {
    return previewEntry;
  }
  removePrivatePreviewEntry(myUserId, conversationItem.partner_id, previewScope);
  return null;
};

const getValidatedGroupPreviewEntry = (conversationItem) => {
  const previewScope = getPreviewStorageScope();
  const previewEntry = getGroupPreviewEntry(myUserId, conversationItem.group_id, previewScope);
  if (!previewEntry) {
    return null;
  }
  if (conversationItem?.last_message_type !== 'sender_key_distribution'
      && isPreviewEntryAlignedWithConversation(previewEntry, conversationItem)) {
    return previewEntry;
  }
  removeGroupPreviewEntry(myUserId, conversationItem.group_id, previewScope);
  return null;
};

const getConversationActivityTimestamp = (contact) => {
  const activityTs = getTimestampMs(contact?.lastActivityAt);
  if (activityTs) {
    return activityTs;
  }
  if (contact?.isTemporary) {
    const draftMeta = getDraftMetaForConversation(contact.id, contact.type);
    return getTimestampMs(draftMeta.updatedAt);
  }
  return 0;
};

const applyConversationActivity = (contact, activityAt) => {
  const parsed = parseDisplayTimestamp(activityAt);
  if (!contact || !parsed) {
    return;
  }
  contact.lastActivityAt = parsed.toISOString();
  contact.lastTime = formatClockTime(parsed);
};

const sortContactsByActivity = (contacts) => {
  return [...contacts].map((contact, index) => ({
    contact,
    index,
    ts: getConversationActivityTimestamp(contact),
  })).sort((left, right) => {
    if (right.ts !== left.ts) {
      return right.ts - left.ts;
    }
    return left.index - right.index;
  }).map((entry) => entry.contact);
};

const sortContactListByActivity = () => {
  contactList.value = sortContactsByActivity(contactList.value);
};

const syncTemporaryPrivateContacts = (users) => {
  if (!users?.length) return;

  contactList.value = contactList.value.map(contact => {
    if (contact.type !== 'private' || !contact.isTemporary) return contact;

    const matchedUser = users.find(user => user.id === contact.id);
    if (!matchedUser) return contact;

    return {
      ...contact,
      username: matchedUser.username,
      avatar: matchedUser.avatar || contact.avatar || '',
      isOnline: typeof matchedUser.is_online === 'boolean' ? matchedUser.is_online : contact.isOnline,
      canChat: typeof matchedUser.can_start_chat === 'boolean' ? matchedUser.can_start_chat : contact.canChat
    };
  });
};

const refreshTemporaryPrivateContactAccess = async (userId) => {
  const temporaryContact = contactList.value.find(contact => {
    return contact.id === userId && contact.type === 'private' && contact.isTemporary;
  });
  if (!temporaryContact) return;

  const friend = friendsList.value.find(item => item.id === userId);
  const searchUser = searchResults.users.find(item => item.id === userId)
    || createGroupSearchResults.value.find(item => item.id === userId)
    || inviteSearchResults.value.find(item => item.id === userId)
    || allUsers.value.find(item => item.id === userId);

  contactList.value = contactList.value.map(contact => {
    if (!(contact.id === userId && contact.type === 'private' && contact.isTemporary)) {
      return contact;
    }

    return {
      ...contact,
      username: friend?.username || searchUser?.username || contact.username,
      avatar: friend?.avatar ?? searchUser?.avatar ?? contact.avatar ?? '',
      isOnline: typeof searchUser?.is_online === 'boolean' ? searchUser.is_online : contact.isOnline,
      canChat: Boolean(friend)
    };
  });

  if (currentChatType.value === 'private' && currentChatId.value === userId && !currentChatCanSend.value) {
    inputText.value = '';
    ElMessage.info(t('privateChatLocked'));
  }
};

const refreshAllTemporaryPrivateContactAccess = () => {
  contactList.value
    .filter(contact => contact.type === 'private' && contact.isTemporary)
    .forEach(contact => refreshTemporaryPrivateContactAccess(contact.id));
};

const mergeUniqueById = (existingItems, newItems) => {
  const mergedMap = new Map(existingItems.map(item => [item.id, item]));
  newItems.forEach(item => {
    mergedMap.set(item.id, item);
  });
  return Array.from(mergedMap.values());
};

const hasConversation = (id, type) => {
  return contactList.value.some(contact => contact.id === id && contact.type === type);
};

const showSearchResults = computed(() => searchText.value.trim().length > 0);

const filteredContacts = computed(() => {
  if (!searchText.value) return contactList.value;
  const keyword = searchText.value.trim().toLowerCase();
  if (!keyword) return contactList.value;
  return contactList.value.filter(u => u.username.toLowerCase().includes(keyword));
});

const searchMatchedChats = computed(() => {
  const matchingGroupIds = new Set(searchResults.groups.map(group => group.id));
  return filteredContacts.value.filter(contact => {
    return contact.type !== 'group' || !matchingGroupIds.has(contact.id);
  });
});

const discoveredUsers = computed(() => {
  return searchResults.users.filter(user => !hasConversation(user.id, 'private'));
});

const searchGroupEntries = computed(() => {
  return searchResults.groups.map(group => {
    const conversation = contactList.value.find(contact => {
      return contact.id === group.id && contact.type === 'group';
    });
    return {
      ...group,
      conversation,
      conversationIndex: conversation
        ? contactList.value.findIndex(contact => contact.id === group.id && contact.type === 'group')
        : Number.POSITIVE_INFINITY,
      lastActivityTs: group.last_activity_ts || 0
    };
  }).sort((left, right) => {
    if (left.conversation && right.conversation) {
      return left.conversationIndex - right.conversationIndex;
    }
    if (left.conversation) return -1;
    if (right.conversation) return 1;
    if (left.lastActivityTs !== right.lastActivityTs) {
      return right.lastActivityTs - left.lastActivityTs;
    }
    return left.name.localeCompare(right.name);
  });
});

const createGroupCandidates = computed(() => {
  if (!createGroupMemberSearch.value.trim() && createGroupSearchLoading.value) {
    return [];
  }

  if (createGroupMemberSearch.value.trim()) {
    if (createGroupSearchLoading.value) {
      return filterUsersByKeyword(allUsers.value, createGroupMemberSearch.value);
    }
    return createGroupSearchResults.value;
  }
  return allUsers.value;
});

const filterUsersByKeyword = (users, keyword) => {
  const normalized = keyword.trim().toLowerCase();
  if (!normalized) return users;
  return users.filter(user => user.username.toLowerCase().includes(normalized));
};

const filteredCreateGroupCandidates = computed(() => {
  return filterUsersByKeyword(createGroupCandidates.value, createGroupMemberSearch.value);
});

// 当前群聊中可邀请的用户。
const availableContacts = computed(() => {
  const currentMemberIds = groupMembers.value.map(m => m.id);
  if (inviteSearchLoading.value || inviteAccessLoading.value) {
    return [];
  }

  const sourceUsers = inviteSearch.value.trim()
    ? (inviteSearchLoading.value ? filterUsersByKeyword(allUsers.value, inviteSearch.value) : inviteSearchResults.value)
    : allUsers.value;
  const pendingInviteIds = new Set(currentGroupInvites.value.map(invite => invite.invitee.id));
  return sourceUsers.filter(user => {
    return !currentMemberIds.includes(user.id) && !pendingInviteIds.has(user.id);
  });
});

const filteredAvailableContacts = computed(() => {
  return filterUsersByKeyword(availableContacts.value, inviteSearch.value);
});

const refreshSearchResultsIfNeeded = async () => {
  const keyword = searchText.value.trim();
  if (!keyword) return;
  resetMainSearchResults();
  searchResults.loading = true;
  await performSearch(keyword);
};

const resetMainSearchResults = () => {
  userLoadMoreAbortController?.abort();
  groupLoadMoreAbortController?.abort();
  userLoadMoreAbortController = null;
  groupLoadMoreAbortController = null;
  searchResults.users = [];
  searchResults.groups = [];
  searchResults.loading = false;
  searchResults.error = '';
  searchResults.usersHasMore = false;
  searchResults.groupsHasMore = false;
  searchResults.usersNextOffset = 0;
  searchResults.groupsNextOffset = 0;
  searchResults.groupsAnchorTs = null;
  searchResults.usersPaginationTouched = false;
  searchResults.groupsPaginationTouched = false;
  searchResults.usersLoadingMore = false;
  searchResults.groupsLoadingMore = false;
  if (contactListRef.value) {
    contactListRef.value.scrollTop = 0;
  }
  resetScrollUi('main');
};

const syncProfileFromAuthPayload = (payload = {}) => {
  if (payload.user_id !== undefined && payload.user_id !== null) {
    myUserId = Number(payload.user_id || 0);
    myUserIdState.value = myUserId;
  }

  if (payload.username) {
    myUsername.value = payload.username;
  } else {
    myUsername.value = localStorage.getItem('username') || myUsername.value || '';
  }

  if (Object.prototype.hasOwnProperty.call(payload, 'avatar')) {
    myAvatar.value = payload.avatar || '';
  } else {
    myAvatar.value = localStorage.getItem('avatar') || myAvatar.value || '';
  }

  if (payload.feature_flags) {
    sessionFeatureFlags.e2ee_private_enabled = payload.feature_flags.e2ee_private_enabled ?? sessionFeatureFlags.e2ee_private_enabled;
    sessionFeatureFlags.e2ee_group_enabled = payload.feature_flags.e2ee_group_enabled ?? sessionFeatureFlags.e2ee_group_enabled;
  }

  syncIdentityFromAccessToken();
  conversationDrafts.value = loadConversationDrafts();
};

const handleAuthChanged = (event) => {
  syncProfileFromAuthPayload(event.detail || {});
};

const getDeviceStorageScope = () => `user:${myUserId || 'guest'}`;

const refreshCurrentDevicePrekeysIfNeeded = async (deviceState, serverDevice) => {
  if (!serverDevice?.device_id || (serverDevice.one_time_prekey_count || 0) >= 5) {
    return deviceState;
  }

  try {
    const refreshData = await buildPrekeyRefreshPayload(deviceState);
    await axios.post(
      `${API_BASE}/e2ee/devices/${encodeURIComponent(serverDevice.device_id)}/prekeys/refresh`,
      refreshData.payload,
      {headers: {Authorization: `Bearer ${token}`}}
    );

    return refreshData.updatedState;
  } catch (e) {
    console.error(e);
    return deviceState;
  }
};

const bootstrapCurrentDevice = async (deviceState) => {
  const bootstrapRes = await axios.post(
    `${API_BASE}/e2ee/devices/bootstrap`,
    buildBootstrapPayload(deviceState),
    {headers: {Authorization: `Bearer ${token}`}}
  );

  applyAuthResponse(bootstrapRes.data);
  syncProfileFromAuthPayload(bootstrapRes.data);
  currentDeviceId.value = bootstrapRes.data.device?.device_id || deviceState.deviceId;

  let nextDeviceState = {
    ...deviceState,
    deviceId: bootstrapRes.data.device?.device_id || deviceState.deviceId,
    activeDeviceCount: bootstrapRes.data.active_device_count || deviceState.activeDeviceCount || 1,
    registeredAt: bootstrapRes.data.device?.created_at || deviceState.registeredAt || new Date().toISOString()
  };

  nextDeviceState = await refreshCurrentDevicePrekeysIfNeeded(nextDeviceState, bootstrapRes.data.device);

  await saveStoredDeviceState(getDeviceStorageScope(), nextDeviceState);
  return nextDeviceState;
};

const rebindCurrentBrowserDevice = async (serverDevice, activeDeviceCount) => {
  const recoverySessionScope = `user:${myUserId || 'guest'}:device:${serverDevice?.device_id || 'unknown'}`;
  await clearStoredDeviceState(getDeviceStorageScope());
  await clearStoredSessionStates(recoverySessionScope);
  await clearGroupSenderKeyStates(recoverySessionScope);
  await clearOutboxMessages(recoverySessionScope);
  await clearCachedPlaintexts(recoverySessionScope);

  const replacementState = await generateDeviceState({
    deviceId: serverDevice?.device_id,
    deviceName: serverDevice?.device_name || undefined,
    platform: serverDevice?.platform || undefined,
    registrationId: serverDevice?.registration_id || undefined,
    registeredAt: serverDevice?.created_at || null,
  });

  const nextState = await bootstrapCurrentDevice({
    ...replacementState,
    userId: myUserId,
    activeDeviceCount: activeDeviceCount || 1,
  });
  currentDeviceState.value = nextState;
  return nextState;
};

const ensureDeviceBootstrap = async () => {
  const storageScope = getDeviceStorageScope();
  const storedDeviceState = await loadStoredDeviceState(storageScope);
  let serverDevice = null;
  let activeDeviceCount = storedDeviceState?.activeDeviceCount || 0;

  try {
    const currentDeviceRes = await axios.get(`${API_BASE}/e2ee/devices/me`, {
      headers: {Authorization: `Bearer ${token}`}
    });
    serverDevice = currentDeviceRes.data.device || null;
    activeDeviceCount = currentDeviceRes.data.active_device_count || activeDeviceCount;
  } catch (e) {
    if (!e.response || ![404, 409].includes(e.response.status)) {
      throw e;
    }
  }

  if (!storedDeviceState && activeDeviceCount > 0 && serverDevice) {
    return await rebindCurrentBrowserDevice(serverDevice, activeDeviceCount);
  }

  if (serverDevice) {
    currentDeviceId.value = serverDevice.device_id || '';
  }

  if (storedDeviceState && serverDevice && storedDeviceState.deviceId === serverDevice.device_id) {
    let syncedState = {
      ...storedDeviceState,
      userId: myUserId,
      deviceId: serverDevice.device_id,
      activeDeviceCount,
      registeredAt: serverDevice.created_at || storedDeviceState.registeredAt || new Date().toISOString()
    };
    syncedState = await refreshCurrentDevicePrekeysIfNeeded(syncedState, serverDevice);
    await saveStoredDeviceState(storageScope, syncedState);
    currentDeviceState.value = syncedState;
    return syncedState;
  }

  let bootstrapState = storedDeviceState;
  if (!bootstrapState || (serverDevice && bootstrapState.deviceId !== serverDevice.device_id)) {
    bootstrapState = await generateDeviceState();
  }

  bootstrapState = {
    ...bootstrapState,
    userId: myUserId,
    activeDeviceCount,
  };

  const finalState = await bootstrapCurrentDevice(bootstrapState);
  currentDeviceState.value = finalState;
  return finalState;
};

const getSessionStorageScope = () => `user:${myUserId || 'guest'}:device:${currentDeviceId.value || 'unknown'}`;
const getPreviewStorageScope = () => currentDeviceId.value || 'default';

let _cacheKeyPromise = null;
let _cacheKeyDeviceId = null;
const getCacheEncryptionKey = async () => {
  if (!currentDeviceState.value) return null;
  const deviceId = currentDeviceState.value.deviceId;
  if (_cacheKeyPromise && _cacheKeyDeviceId === deviceId) return _cacheKeyPromise;
  _cacheKeyDeviceId = deviceId;
  _cacheKeyPromise = deriveCacheEncryptionKey(currentDeviceState.value);
  return _cacheKeyPromise;
};

const updateCurrentDeviceActiveCount = async (nextCount) => {
  if (!currentDeviceState.value || !Number.isFinite(Number(nextCount))) {
    return;
  }

  const normalizedCount = Math.max(0, Number(nextCount));
  currentDeviceState.value = {
    ...currentDeviceState.value,
    activeDeviceCount: normalizedCount,
  };
  await saveStoredDeviceState(getDeviceStorageScope(), currentDeviceState.value);
};

const handleCurrentDeviceRevoked = async () => {
  if (deviceRevocationInProgress.value) {
    return;
  }
  deviceRevocationInProgress.value = true;

  if (currentDeviceId.value) {
    const sessionScope = getSessionStorageScope();
    await clearOutboxMessages(sessionScope).catch(console.error);
    await clearStoredSessionStates(sessionScope).catch(console.error);
    await clearGroupSenderKeyStates(sessionScope).catch(console.error);
    await clearCachedPlaintexts(sessionScope).catch(console.error);
  }
  await clearStoredDeviceState(getDeviceStorageScope()).catch(console.error);
  await logoutSession().catch(() => {});
  token = '';
  if (socket) {
    socket.close();
  }
  window.location.replace(router.resolve('/').href);
};

const isRevokedSocketCloseEvent = (event) => {
  return event?.code === 4001 || event?.reason === 'device_revoked';
};

const getPartnerIdForPrivateMessage = (messageItem) => {
  return messageItem.sender_user_id === myUserId ? messageItem.partner_id : messageItem.sender_user_id;
};

const updatePrivateConversationPreview = (partnerId, plaintext, createdAt, isOwnMessage, msgType = 'text', {bumpConversation = true} = {}) => {
  const normalizedPlaintext = msgType === 'image'
    ? '[Image]'
    : (msgType === 'file' ? '[File]' : plaintext);
  const previewText = buildPrivatePreviewText(normalizedPlaintext, isOwnMessage);
  const previewTimestamp = createdAt || new Date().toISOString();
  savePrivatePreviewEntry(myUserId, partnerId, {
    text: previewText,
    timestamp: previewTimestamp,
  }, getPreviewStorageScope());

  const contact = contactList.value.find((item) => item.id === partnerId && item.type === 'private');
  if (contact) {
    contact.lastMessage = previewText;
    applyConversationActivity(contact, previewTimestamp);
    if (bumpConversation) {
      sortContactListByActivity();
    }
  }
};

const updatePrivateConversationRecallPreview = (partnerId, createdAt, isOwnMessage, {bumpConversation = true} = {}) => {
  const previewText = buildConversationRecallPreview({chatType: 'private', isOwnMessage});
  const previewTimestamp = createdAt || new Date().toISOString();
  savePrivatePreviewEntry(myUserId, partnerId, {
    text: previewText,
    timestamp: previewTimestamp,
  }, getPreviewStorageScope());

  const contact = contactList.value.find((item) => item.id === partnerId && item.type === 'private');
  if (contact) {
    contact.lastMessage = previewText;
    applyConversationActivity(contact, previewTimestamp);
    if (bumpConversation) {
      sortContactListByActivity();
    }
  }
};

const upsertE2EEConversationContact = (conversationItem) => {
  const previewEntry = getValidatedPrivatePreviewEntry(conversationItem);
  const existing = getMatchedConversationContact(
    contactList.value.find((item) => item.id === conversationItem.partner_id && item.type === 'private'),
    conversationItem.id,
  );
  const recalledPreview = conversationItem.last_message_is_recalled
    ? buildConversationRecallPreview({
      chatType: 'private',
      isOwnMessage: Number(conversationItem.last_message_sender_user_id) === Number(myUserId),
    })
    : '';
  const previewTimestamp = conversationItem.last_message_created_at || conversationItem.last_message_at || previewEntry?.timestamp || existing?.lastActivityAt || null;
  if (recalledPreview && previewTimestamp) {
    savePrivatePreviewEntry(myUserId, conversationItem.partner_id, {
      text: recalledPreview,
      timestamp: previewTimestamp,
    }, getPreviewStorageScope());
  }
  const patch = {
    id: conversationItem.partner_id,
    username: conversationItem.username,
    avatar: conversationItem.avatar || '',
    type: 'private',
    e2eeConversationId: conversationItem.id,
    protocolVersion: conversationItem.protocol_version,
    lastMessage: recalledPreview || previewEntry?.text || existing?.lastMessage || '',
    lastTime: previewTimestamp ? formatClockTime(previewTimestamp) : (existing?.lastTime || ''),
    lastActivityAt: pickLatestTimestamp(previewTimestamp, existing?.lastActivityAt, conversationItem.last_message_at),
  };

  if (existing) {
    Object.assign(existing, patch);
    return existing;
  }

  return ensureConversationEntry({
    ...patch,
    isOnline: false,
    unreadCount: 0,
    canChat: true,
  });
};

const updateGroupConversationPreview = (groupId, plaintext, createdAt, senderName, isOwnMessage, msgType = 'text', {bumpConversation = true} = {}) => {
  const normalizedPlaintext = msgType === 'image'
    ? '[Image]'
    : (msgType === 'file' ? '[File]' : plaintext);
  const previewText = isOwnMessage ? `You: ${normalizedPlaintext}` : `${senderName || 'Unknown'}: ${normalizedPlaintext}`;
  const previewTimestamp = createdAt || new Date().toISOString();
  saveGroupPreviewEntry(myUserId, groupId, {
    text: previewText,
    timestamp: previewTimestamp,
  }, getPreviewStorageScope());
  const contact = contactList.value.find((item) => item.id === groupId && item.type === 'group');
  if (contact) {
    contact.lastMessage = previewText;
    contact.lastTime = formatClockTime(previewTimestamp);
    applyConversationActivity(contact, previewTimestamp);
    if (bumpConversation) {
      sortContactListByActivity();
    }
  }
};

const updateGroupConversationRecallPreview = (groupId, createdAt, senderName, isOwnMessage, {bumpConversation = true} = {}) => {
  const previewText = buildConversationRecallPreview({chatType: 'group', senderName, isOwnMessage});
  const previewTimestamp = createdAt || new Date().toISOString();
  saveGroupPreviewEntry(myUserId, groupId, {
    text: previewText,
    timestamp: previewTimestamp,
  }, getPreviewStorageScope());
  const contact = contactList.value.find((item) => item.id === groupId && item.type === 'group');
  if (contact) {
    contact.lastMessage = previewText;
    contact.lastTime = formatClockTime(previewTimestamp);
    applyConversationActivity(contact, previewTimestamp);
    if (bumpConversation) {
      sortContactListByActivity();
    }
  }
};

const buildOutgoingPlaceholderMessage = (item) => ({
  id: `local:${item.clientMessageId}`,
  clientMessageId: item.clientMessageId,
  from: myUserId,
  content: item.plaintext,
  msg_type: item.msgType,
  username: myUsername.value,
  avatar: myAvatar.value,
  timestamp: item.createdAt,
  isE2EE: true,
  protocolVersion: 'e2ee_v1',
  deliveryStatus: item.status || 'queued',
  isLocalOnly: true,
});

const updateMessageStatusByClientId = (clientMessageId, statusValue) => {
  if (!clientMessageId) return;
  messages.value = messages.value.map((message) => {
    if (message.clientMessageId === clientMessageId) {
      return {...message, deliveryStatus: statusValue};
    }
    return message;
  });
};

const upsertOutgoingPlaceholderMessage = (item) => {
  const isCurrentConversation = Number(currentChatId.value) === Number(item.chatId) && currentChatType.value === item.chatType;
  const placeholder = buildOutgoingPlaceholderMessage(item);
  const existingIndex = messages.value.findIndex((message) => message.clientMessageId === item.clientMessageId);
  if (existingIndex >= 0) {
    messages.value[existingIndex] = {
      ...messages.value[existingIndex],
      ...placeholder,
      id: messages.value[existingIndex].id,
    };
  } else if (isCurrentConversation) {
    messages.value.push(placeholder);
    scrollToBottom();
  }

  if (item.chatType === 'private') {
    updatePrivateConversationPreview(item.chatId, item.plaintext, item.createdAt, true, item.msgType);
  } else {
    updateGroupConversationPreview(item.chatId, item.plaintext, item.createdAt, myUsername.value, true, item.msgType);
  }
};

const mergeConversationOutboxMessages = async (conversationMessages, contact) => {
  const outboxItems = (await listOutboxMessages(getSessionStorageScope())).filter((item) => {
    return Number(item.chatId) === Number(contact.id) && item.chatType === contact.type;
  });
  if (!outboxItems.length) {
    return conversationMessages;
  }

  const serverClientIds = new Set(conversationMessages.map((message) => message.clientMessageId).filter(Boolean));
  for (const outboxItem of outboxItems) {
    if (serverClientIds.has(outboxItem.clientMessageId)) {
      await removeOutboxMessage(getSessionStorageScope(), outboxItem.clientMessageId);
      continue;
    }
    conversationMessages.push(buildOutgoingPlaceholderMessage(outboxItem));
  }

  conversationMessages.sort((left, right) => {
    return new Date(left.timestamp || 0).getTime() - new Date(right.timestamp || 0).getTime();
  });
  return conversationMessages;
};

const upsertE2EEGroupConversationContact = (conversationItem) => {
  const previewEntry = getValidatedGroupPreviewEntry(conversationItem);
  const existing = getMatchedConversationContact(
    contactList.value.find((item) => item.id === conversationItem.group_id && item.type === 'group'),
    conversationItem.id,
  );
  const recalledPreview = conversationItem.last_message_is_recalled
    ? buildConversationRecallPreview({
      chatType: 'group',
      senderName: conversationItem.last_message_sender_username,
      isOwnMessage: Number(conversationItem.last_message_sender_user_id) === Number(myUserId),
    })
    : '';
  const previewTimestamp = conversationItem.last_message_created_at || conversationItem.last_message_at || previewEntry?.timestamp || existing?.lastActivityAt || null;
  if (recalledPreview && previewTimestamp) {
    saveGroupPreviewEntry(myUserId, conversationItem.group_id, {
      text: recalledPreview,
      timestamp: previewTimestamp,
    }, getPreviewStorageScope());
  }
  const patch = {
    id: conversationItem.group_id,
    username: conversationItem.username,
    avatar: conversationItem.avatar || '',
    type: 'group',
    e2eeConversationId: conversationItem.id,
    protocolVersion: conversationItem.protocol_version,
    lastMessage: recalledPreview || previewEntry?.text || existing?.lastMessage || '',
    lastTime: previewTimestamp ? formatClockTime(previewTimestamp) : (existing?.lastTime || ''),
    lastActivityAt: pickLatestTimestamp(previewEntry?.timestamp, existing?.lastActivityAt, previewTimestamp, conversationItem.last_message_at),
  };

  if (existing) {
    Object.assign(existing, patch);
    return existing;
  }

  return ensureConversationEntry({
    ...patch,
    isOnline: true,
    unreadCount: 0,
    canChat: true,
  });
};

const hydrateGroupConversationPreview = async (contact) => {
  if (!contact?.e2eeConversationId || contact.type !== 'group' || !currentDeviceState.value) {
    return;
  }

  const hydrationKey = `${contact.id}:${contact.e2eeConversationId}`;
  if (pendingGroupPreviewHydrations.has(hydrationKey)) {
    return;
  }

  pendingGroupPreviewHydrations.add(hydrationKey);
  try {
    const response = await axios.get(`${API_BASE}/e2ee/conversations/${contact.e2eeConversationId}/messages`, {
      headers: {Authorization: `Bearer ${token}`}
    });
    await decryptGroupHistoryMessages(response.data || [], contact);
  } catch (error) {
    console.error('Failed to hydrate group preview', contact.id, error);
  } finally {
    pendingGroupPreviewHydrations.delete(hydrationKey);
  }
};

const hydrateMissingGroupConversationPreviews = async (contacts = contactList.value) => {
  const candidates = contacts.filter((contact) => {
    return contact.type === 'group'
      && contact.e2eeConversationId
      && contact.lastActivityAt
      && !contact.lastMessage;
  });

  if (!candidates.length) {
    return;
  }

  await Promise.allSettled(candidates.map((contact) => hydrateGroupConversationPreview(contact)));
};

const parseEnvelopePayload = (value) => {
  if (!value) return null;
  return typeof value === 'string' ? JSON.parse(value) : value;
};

const acknowledgeE2EEMessage = (messageId, statusValue) => {
  if (!isSocketReady()) return;
  socket.send(JSON.stringify({
    type: 'message.ack',
    message_id: messageId,
    status: statusValue,
  }));
};

const decryptE2EEMessageList = async (items) => {
  if (!currentDeviceState.value) {
    throw new Error('当前设备状态不可用');
  }

  const sessionScope = getSessionStorageScope();
  const decryptedMessages = [];

  // Phase 1: try loading all plaintexts from local cache
  const cacheKey = await getCacheEncryptionKey();
  const nonRecalledIds = items.filter((item) => !item.is_recalled).map((item) => item.message_id);
  const cachedPlaintexts = cacheKey && nonRecalledIds.length
    ? await loadCachedPlaintextBatch(sessionScope, nonRecalledIds, cacheKey).catch(() => new Map())
    : new Map();
  const allCached = nonRecalledIds.length > 0 && nonRecalledIds.every((id) => cachedPlaintexts.has(id));

  if (allCached) {
    for (const item of items) {
      if (item.is_recalled) {
        const receiptSummary = cacheReceiptSummary(item.message_id, item.receipt_summary, item.delivery_status || 'sent');
        decryptedMessages.push({
          id: item.message_id, clientMessageId: item.client_message_id, from: item.sender_user_id,
          content: '', msg_type: item.message_type, username: item.username, avatar: item.avatar || '',
          timestamp: item.created_at, conversationId: item.conversation_id, partnerId: item.partner_id,
          isE2EE: true, protocolVersion: item.protocol_version || 'e2ee_v1',
          deliveryStatus: receiptSummary.status, receiptSummary,
          isRecalled: true, recalledAt: item.recalled_at || null, recalledByUserId: item.recalled_by_user_id || null,
        });
        continue;
      }
      const plaintext = cachedPlaintexts.get(item.message_id);
      const receiptSummary = cacheReceiptSummary(item.message_id, item.receipt_summary, item.delivery_status || 'sent');
      decryptedMessages.push({
        id: item.message_id, clientMessageId: item.client_message_id, from: item.sender_user_id,
        content: plaintext, msg_type: item.message_type, username: item.username, avatar: item.avatar || '',
        timestamp: item.created_at, conversationId: item.conversation_id, partnerId: item.partner_id,
        isE2EE: true, protocolVersion: item.protocol_version || 'e2ee_v1',
        deliveryStatus: receiptSummary.status, receiptSummary,
      });
      if (['image', 'file'].includes(item.message_type)) {
        const descriptor = parseEncryptedAttachmentDescriptor(plaintext);
        if (descriptor) loadEncryptedAttachmentUrl(descriptor).catch(console.error);
      }
    }
    return decryptedMessages;
  }

  // Phase 2: cache miss – decrypt all, then batch-cache results
  const sessionSnapshots = new Map();
  const toCache = [];

  const findSessionFallback = async (senderDeviceId) => {
    const sessions = await listDeviceSessions(sessionScope);
    for (const session of sessions) {
      if (session.remoteDeviceId === senderDeviceId) {
        return session;
      }
    }
    for (const session of sessions) {
      if (session.sendingRatchetKeyPair && session.rootKey) {
        return session;
      }
    }
    return null;
  };

  for (const item of items) {
    if (item.is_recalled) {
      const receiptSummary = cacheReceiptSummary(item.message_id, item.receipt_summary, item.delivery_status || 'sent');
      decryptedMessages.push({
        id: item.message_id, clientMessageId: item.client_message_id, from: item.sender_user_id,
        content: '', msg_type: item.message_type, username: item.username, avatar: item.avatar || '',
        timestamp: item.created_at, conversationId: item.conversation_id, partnerId: item.partner_id,
        isE2EE: true, protocolVersion: item.protocol_version || 'e2ee_v1',
        deliveryStatus: receiptSummary.status, receiptSummary,
        isRecalled: true, recalledAt: item.recalled_at || null, recalledByUserId: item.recalled_by_user_id || null,
      });
      continue;
    }

    const envelope = parseEnvelopePayload(item.envelope);
    const sessionKey = item.envelope_type === 'local' ? '__local__' : (item.sender_device_id || envelope?.sender_device_id || 'unknown');
    const fromSnapshot = sessionKey !== '__local__' && sessionSnapshots.has(sessionKey);
    let storedSession = sessionKey === '__local__'
      ? null
      : (fromSnapshot ? sessionSnapshots.get(sessionKey) : await loadDeviceSession(sessionScope, sessionKey));

    if (!storedSession && sessionKey !== '__local__'
        && item.sender_user_id !== myUserId) {
      const fallback = await findSessionFallback(sessionKey);
      if (fallback) {
        storedSession = fallback;
      }
    }
    
    let decrypted = {plaintext: ''};
    let isDecryptionError = false;

    try {
      decrypted = await decryptEnvelopeForHistory({
        deviceState: currentDeviceState.value,
        sessionState: storedSession,
        envelope,
        metadata: item,
      });

      if (sessionKey !== '__local__' && decrypted.sessionState) {
        sessionSnapshots.set(sessionKey, decrypted.sessionState);
      }
    } catch (err) {
      console.warn('Failed to decrypt private history message:', err);
      const availableKeys = storedSession?.usedMessageKeys ? Object.keys(storedSession.usedMessageKeys).length : 0;
      const targetPrefix = (envelope?.dh_ratchet_key || 'initial').substring(0, 16);
      decrypted.plaintext = `[解密失败: ${err.name}] keys=${availableKeys}, target=${targetPrefix}:${envelope?.counter}, recvC=${storedSession?.recvCounter}`;
      isDecryptionError = true;
    }

    if (!isDecryptionError) {
      toCache.push({messageId: item.message_id, plaintext: decrypted.plaintext});
    }

    const receiptSummary = cacheReceiptSummary(item.message_id, item.receipt_summary, item.delivery_status || 'sent');
    decryptedMessages.push({
      id: item.message_id, clientMessageId: item.client_message_id, from: item.sender_user_id,
      content: decrypted.plaintext, msg_type: item.message_type, username: item.username, avatar: item.avatar || '',
      timestamp: item.created_at, conversationId: item.conversation_id, partnerId: item.partner_id,
      isE2EE: true, protocolVersion: item.protocol_version || 'e2ee_v1',
      deliveryStatus: receiptSummary.status, receiptSummary, isDecryptionError,
    });

    if (!isDecryptionError && ['image', 'file'].includes(item.message_type)) {
      const descriptor = parseEncryptedAttachmentDescriptor(decrypted.plaintext);
      if (descriptor) {
        loadEncryptedAttachmentUrl(descriptor).catch(console.error);
      }
    }
  }

  if (cacheKey && toCache.length) {
    saveCachedPlaintextBatch(sessionScope, toCache, cacheKey).catch(console.error);
  }

  return decryptedMessages;
};

const applyPrivateE2EEMessage = async (eventPayload) => {
  if (eventPayload.message?.is_recalled) {
    await applyMessageRecalledEvent(eventPayload);
    return;
  }

  if (!currentDeviceState.value) return;

  const targetPayload = (eventPayload.payloads || []).find((item) => item.recipient_device_id === currentDeviceId.value);
  if (!targetPayload) return;

  let decrypted;
  try {
    decrypted = await decryptIncomingEnvelope({
      scopeKey: getSessionStorageScope(),
      deviceState: currentDeviceState.value,
      envelope: parseEnvelopePayload(targetPayload.envelope),
      metadata: {
        sender_user_id: eventPayload.message.sender_user_id,
      },
    });
  } catch (decryptError) {
    console.error('[E2EE] Failed to decrypt private message:', decryptError,
      'sender_device_id:', eventPayload.message.sender_device_id,
      'envelope_type:', targetPayload.envelope_type);
    // Clear potentially corrupted session so next prekey message can rebuild cleanly
    const brokenEnvelope = parseEnvelopePayload(targetPayload.envelope);
    if (brokenEnvelope?.sender_device_id) {
      await clearStoredSessionState(getSessionStorageScope(), brokenEnvelope.sender_device_id);
    }
    decrypted = {plaintext: '[解密失败]'};
  }

  if (decrypted.plaintext && decrypted.plaintext !== '[解密失败]') {
    getCacheEncryptionKey().then((ck) => {
      if (ck) saveCachedPlaintext(getSessionStorageScope(), eventPayload.message.id, decrypted.plaintext, ck).catch(console.error);
    });
  }

  const partnerId = eventPayload.partner_id;
  const isOwnMessage = eventPayload.message.sender_user_id === myUserId;
  if (isOwnMessage && eventPayload.message.client_message_id) {
    await removeOutboxMessage(getSessionStorageScope(), eventPayload.message.client_message_id);
    const acceptedStatus = getAcceptedOwnDeliveryStatus(eventPayload.message.id);
    deliveryStatusCache[eventPayload.message.id] = acceptedStatus;
    messageReceiptCache[eventPayload.message.id] = messageReceiptCache[eventPayload.message.id] || normalizeReceiptSummary(null, acceptedStatus);
  }
  const existingContact = contactList.value.find((item) => item.id === partnerId && item.type === 'private');
  const partnerUsername = isOwnMessage
    ? (existingContact?.username || (currentChatType.value === 'private' && currentChatId.value === partnerId ? currentChatUser.value?.username : null) || String(partnerId))
    : eventPayload.message.username;
  const partnerAvatar = isOwnMessage
    ? (existingContact?.avatar || (currentChatType.value === 'private' && currentChatId.value === partnerId ? currentChatUser.value?.avatar : null) || '')
    : (eventPayload.message.avatar || '');
  const contact = upsertE2EEConversationContact({
    id: eventPayload.conversation_id,
    partner_id: partnerId,
    username: partnerUsername,
    avatar: partnerAvatar,
    protocol_version: eventPayload.message.protocol_version,
  });

  contact.e2eeConversationId = eventPayload.conversation_id;
  updatePrivateConversationPreview(
    partnerId,
    decrypted.plaintext,
    eventPayload.message.created_at,
    isOwnMessage,
    eventPayload.message.message_type,
  );

  const isCurrentChat = currentChatType.value === 'private' && currentChatId.value === partnerId;
  if (isCurrentChat) {
    const existingIndex = messages.value.findIndex((message) => {
      return message.id === eventPayload.message.id || message.clientMessageId === eventPayload.message.client_message_id;
    });
    const nextMessage = {
      id: eventPayload.message.id,
      clientMessageId: eventPayload.message.client_message_id,
      from: eventPayload.message.sender_user_id,
      content: decrypted.plaintext,
      msg_type: eventPayload.message.message_type,
      username: eventPayload.message.username,
      avatar: eventPayload.message.avatar || '',
      timestamp: eventPayload.message.created_at || null,
      isE2EE: true,
      protocolVersion: eventPayload.message.protocol_version || 'e2ee_v1',
      deliveryStatus: deliveryStatusCache[eventPayload.message.id] || 'sent',
      receiptSummary: messageReceiptCache[eventPayload.message.id] || (isOwnMessage ? normalizeReceiptSummary(null, 'sent') : null),
      isLocalOnly: false,
    };
    if (existingIndex >= 0) {
      messages.value[existingIndex] = {
        ...messages.value[existingIndex],
        ...nextMessage,
      };
    } else {
      messages.value.push(nextMessage);
      scrollToBottom();
    }

    if (['image', 'file'].includes(eventPayload.message.message_type)) {
      const descriptor = parseEncryptedAttachmentDescriptor(decrypted.plaintext);
      if (descriptor) {
        loadEncryptedAttachmentUrl(descriptor).catch(console.error);
      }
    }
    if (!isOwnMessage) {
      acknowledgeE2EEMessage(eventPayload.message.id, 'read');
    }
  } else if (!isOwnMessage) {
    contact.unreadCount = (contact.unreadCount || 0) + 1;
    acknowledgeE2EEMessage(eventPayload.message.id, 'delivered');
  }
};

const ensureSignalSessionsForUserDevices = async (scopeKey, remoteUserId, deviceBundles, {groupId = null} = {}) => {
  const existingSessions = (await listDeviceSessions(scopeKey)).filter((sessionItem) => {
    return Number(sessionItem.remoteUserId) === Number(remoteUserId);
  });
  for (const sessionItem of existingSessions) {
    const bundleDevice = deviceBundles.find((item) => item.device_id === sessionItem.remoteDeviceId);
    if (bundleDevice && sessionItem.remoteIdentityKey && sessionItem.remoteIdentityKey !== bundleDevice.identity_key_public) {
      await clearStoredSessionState(scopeKey, sessionItem.remoteDeviceId);
    }
  }

  const refreshedSessions = (await listDeviceSessions(scopeKey)).filter((sessionItem) => {
    return Number(sessionItem.remoteUserId) === Number(remoteUserId);
  });
  const existingDeviceIds = new Set(refreshedSessions.map((sessionItem) => sessionItem.remoteDeviceId));
  const missingDeviceIds = deviceBundles
    .filter((bundleDevice) => !existingDeviceIds.has(bundleDevice.device_id))
    .map((bundleDevice) => bundleDevice.device_id);

  let consumableBundles = [];
  if (missingDeviceIds.length) {
    if (groupId) {
      const params = new URLSearchParams([
        ['consume', 'true'],
        ['user_id', String(remoteUserId)],
        ...missingDeviceIds.map((deviceId) => ['device_ids', deviceId])
      ]);
      const response = await axios.get(`${API_BASE}/e2ee/groups/${groupId}/member-devices`, {
        headers: {Authorization: `Bearer ${token}`},
        params,
      });
      consumableBundles = (response.data.members || []).find((member) => Number(member.user_id) === Number(remoteUserId))?.devices || [];
    } else {
      const response = await axios.get(`${API_BASE}/e2ee/users/${remoteUserId}/prekey-bundle`, {
        headers: {Authorization: `Bearer ${token}`},
        params: new URLSearchParams(missingDeviceIds.map((deviceId) => ['device_ids', deviceId]))
      });
      consumableBundles = response.data.devices || [];
    }
  }

  for (const bundleDevice of consumableBundles) {
    await createInitiatorSession({
      scopeKey,
      deviceState: currentDeviceState.value,
      remoteUserId,
      bundleDevice,
    });
    existingDeviceIds.add(bundleDevice.device_id);
  }

  return (await listDeviceSessions(scopeKey)).filter((sessionItem) => {
    return Number(sessionItem.remoteUserId) === Number(remoteUserId)
      && deviceBundles.some((bundleDevice) => bundleDevice.device_id === sessionItem.remoteDeviceId);
  });
};

const fetchGroupMemberDeviceDirectory = async (groupId, {force = false} = {}) => {
  if (!force && groupDeviceDirectory[groupId]) {
    return groupDeviceDirectory[groupId];
  }

  const response = await axios.get(`${API_BASE}/e2ee/groups/${groupId}/member-devices`, {
    headers: {Authorization: `Bearer ${token}`}
  });
  groupDeviceDirectory[groupId] = response.data;
  return response.data;
};

const saveGroupSenderKeyFromDistribution = async (distributionPayload) => {
  if (!distributionPayload) return null;
  return await saveReceivedGroupSenderKeyState({
    scopeKey: getSessionStorageScope(),
    groupId: distributionPayload.group_id,
    epoch: distributionPayload.epoch,
    senderDeviceId: distributionPayload.sender_device_id,
    senderKeyBase64: distributionPayload.sender_key,
  });
};

const decryptGroupHistoryMessages = async (items, contact) => {
  const sessionScope = getSessionStorageScope();
  const outputMessages = [];

  // Phase 1: try loading user-visible message plaintexts from cache
  const cacheKey = await getCacheEncryptionKey();
  const userMessageIds = items
    .filter((item) => !item.is_recalled && item.message_type !== 'sender_key_distribution')
    .map((item) => item.message_id);
  const cachedPlaintexts = cacheKey && userMessageIds.length
    ? await loadCachedPlaintextBatch(sessionScope, userMessageIds, cacheKey).catch(() => new Map())
    : new Map();
  const allUserMessagesCached = userMessageIds.length > 0 && userMessageIds.every((id) => cachedPlaintexts.has(id));

  if (allUserMessagesCached) {
    for (const item of items) {
      if (item.is_recalled) {
        const receiptSummary = cacheReceiptSummary(item.message_id, item.receipt_summary, item.delivery_status || 'sent');
        outputMessages.push({
          id: item.message_id, clientMessageId: item.client_message_id, from: item.sender_user_id,
          content: '', msg_type: item.message_type, username: item.username, avatar: item.avatar || '',
          timestamp: item.created_at, conversationId: item.conversation_id, groupId: item.group_id,
          isE2EE: true, protocolVersion: item.protocol_version || 'e2ee_v1',
          deliveryStatus: receiptSummary.status, receiptSummary,
          isRecalled: true, recalledAt: item.recalled_at || null, recalledByUserId: item.recalled_by_user_id || null,
        });
        continue;
      }
      if (item.message_type === 'sender_key_distribution') continue;
      const plaintext = cachedPlaintexts.get(item.message_id);
      const receiptSummary = cacheReceiptSummary(item.message_id, item.receipt_summary, item.delivery_status || 'sent');
      outputMessages.push({
        id: item.message_id, clientMessageId: item.client_message_id, from: item.sender_user_id,
        content: plaintext, msg_type: item.message_type, username: item.username, avatar: item.avatar || '',
        timestamp: item.created_at, conversationId: item.conversation_id, groupId: item.group_id,
        isE2EE: true, protocolVersion: item.protocol_version || 'e2ee_v1',
        deliveryStatus: receiptSummary.status, receiptSummary,
      });
      if (['image', 'file'].includes(item.message_type)) {
        const descriptor = parseEncryptedAttachmentDescriptor(plaintext);
        if (descriptor) loadEncryptedAttachmentUrl(descriptor).catch(console.error);
      }
    }

    if (contact) {
      const latest = outputMessages[outputMessages.length - 1];
      if (latest) {
        if (isMessageRecalled(latest)) {
          updateGroupConversationRecallPreview(contact.id, latest.timestamp, latest.username, latest.from === myUserId, {bumpConversation: false});
        } else {
          updateGroupConversationPreview(contact.id, latest.content, latest.timestamp, latest.username, latest.from === myUserId, latest.msg_type, {bumpConversation: false});
        }
      }
    }
    return outputMessages;
  }

  // Phase 2: cache miss – decrypt all, then batch-cache results
  const signalSessionSnapshots = new Map();
  const toCache = [];
  let missingSenderKey = false;

  for (const item of items) {
    if (item.is_recalled) {
      const receiptSummary = cacheReceiptSummary(item.message_id, item.receipt_summary, item.delivery_status || 'sent');
      outputMessages.push({
        id: item.message_id, clientMessageId: item.client_message_id, from: item.sender_user_id,
        content: '', msg_type: item.message_type, username: item.username, avatar: item.avatar || '',
        timestamp: item.created_at, conversationId: item.conversation_id, groupId: item.group_id,
        isE2EE: true, protocolVersion: item.protocol_version || 'e2ee_v1',
        deliveryStatus: receiptSummary.status, receiptSummary,
        isRecalled: true, recalledAt: item.recalled_at || null, recalledByUserId: item.recalled_by_user_id || null,
      });
      continue;
    }

    const envelope = parseEnvelopePayload(item.envelope);
    if (item.message_type === 'sender_key_distribution') {
      const sessionKey = item.sender_device_id || envelope?.sender_device_id || 'unknown';
      const fromSnapshot = signalSessionSnapshots.has(sessionKey);
      const storedSession = fromSnapshot ? signalSessionSnapshots.get(sessionKey) : resetSessionForReplay(await loadDeviceSession(sessionScope, sessionKey));
      try {
        const decrypted = await decryptEnvelopeForHistory({
          deviceState: currentDeviceState.value,
          sessionState: storedSession,
          envelope,
          metadata: item,
        });
        if (decrypted.sessionState) {
          signalSessionSnapshots.set(sessionKey, decrypted.sessionState);
        }
        await saveGroupSenderKeyFromDistribution(parseSenderKeyDistributionPayload(decrypted.plaintext));
      } catch (err) {
        console.warn('Failed to decrypt sender key distribution:', err);
      }
      continue;
    }

    const senderKeyState = await loadGroupSenderKey({
      scopeKey: sessionScope,
      groupId: item.group_id,
      epoch: envelope.epoch,
      senderDeviceId: item.sender_device_id || envelope.sender_device_id,
    });
    if (!senderKeyState) {
      missingSenderKey = true;
      continue
    }

    let plaintext = '';
    let isDecryptionError = false;
    try {
      plaintext = await decryptGroupSenderKeyMessage({
        senderKeyBase64: senderKeyState.senderKeyBase64,
        envelope,
      });
    } catch (err) {
      console.warn('Failed to decrypt group history message:', err);
      plaintext = '[解密失败]';
      isDecryptionError = true;
    }

    if (!isDecryptionError) {
      toCache.push({messageId: item.message_id, plaintext});
    }

    const receiptSummary = cacheReceiptSummary(item.message_id, item.receipt_summary, item.delivery_status || 'sent');
    outputMessages.push({
      id: item.message_id, clientMessageId: item.client_message_id, from: item.sender_user_id,
      content: plaintext, msg_type: item.message_type, username: item.username, avatar: item.avatar || '',
      timestamp: item.created_at, conversationId: item.conversation_id, groupId: item.group_id,
      isE2EE: true, protocolVersion: item.protocol_version || 'e2ee_v1',
      deliveryStatus: receiptSummary.status, receiptSummary, isDecryptionError,
    });

    if (!isDecryptionError && ['image', 'file'].includes(item.message_type)) {
      const descriptor = parseEncryptedAttachmentDescriptor(plaintext);
      if (descriptor) {
        loadEncryptedAttachmentUrl(descriptor).catch(console.error);
      }
    }
  }

  if (cacheKey && toCache.length) {
    saveCachedPlaintextBatch(sessionScope, toCache, cacheKey).catch(console.error);
  }

  if (missingSenderKey && contact?.id) {
    requestGroupSenderKeysFromMembers(contact.id).catch(console.error);
  }

  if (contact) {
    const latest = outputMessages[outputMessages.length - 1];
    if (latest) {
      if (isMessageRecalled(latest)) {
        updateGroupConversationRecallPreview(contact.id, latest.timestamp, latest.username, latest.from === myUserId, {
          bumpConversation: false,
        });
      } else {
        updateGroupConversationPreview(contact.id, latest.content, latest.timestamp, latest.username, latest.from === myUserId, latest.msg_type, {
          bumpConversation: false,
        });
      }
    }
  }

  return outputMessages;
};

const applyRecalledMessageToCurrentChat = (eventPayload) => {
  const nextMessageMeta = eventPayload.message || {};
  let didUpdate = false;
  messages.value = messages.value.map((message) => {
    if (message.id !== nextMessageMeta.id && message.clientMessageId !== nextMessageMeta.client_message_id) {
      return message;
    }
    didUpdate = true;
    return {
      ...message,
      id: nextMessageMeta.id,
      clientMessageId: nextMessageMeta.client_message_id || message.clientMessageId,
      msg_type: nextMessageMeta.message_type || message.msg_type,
      protocolVersion: nextMessageMeta.protocol_version || message.protocolVersion || 'e2ee_v1',
      timestamp: nextMessageMeta.created_at || message.timestamp || null,
      username: nextMessageMeta.username || message.username,
      avatar: nextMessageMeta.avatar || message.avatar || '',
      content: '',
      isRecalled: true,
      recalledAt: nextMessageMeta.recalled_at || null,
      recalledByUserId: nextMessageMeta.recalled_by_user_id || null,
      isLocalOnly: false,
    };
  });
  return didUpdate;
};

const applyMessageRecalledEvent = async (eventPayload) => {
  const messageMeta = eventPayload.message || {};
  if (!messageMeta.id) {
    return;
  }

  removeCachedPlaintext(getSessionStorageScope(), messageMeta.id).catch(console.error);

  if (eventPayload.chat_type === 'private') {
    const partnerId = eventPayload.partner_id;
    const isOwnMessage = Number(messageMeta.sender_user_id) === Number(myUserId);
    const contact = upsertE2EEConversationContact({
      id: eventPayload.conversation_id,
      partner_id: partnerId,
      username: isOwnMessage
        ? (contactList.value.find((item) => item.id === partnerId && item.type === 'private')?.username || String(partnerId))
        : (messageMeta.username || String(partnerId)),
      avatar: isOwnMessage
        ? (contactList.value.find((item) => item.id === partnerId && item.type === 'private')?.avatar || '')
        : (messageMeta.avatar || ''),
      protocol_version: messageMeta.protocol_version,
      last_message_is_recalled: Boolean(eventPayload.is_latest_message),
      last_message_sender_user_id: messageMeta.sender_user_id,
      last_message_sender_username: messageMeta.username,
      last_message_created_at: messageMeta.created_at,
      last_message_at: messageMeta.created_at,
    });

    if (eventPayload.is_latest_message) {
      updatePrivateConversationRecallPreview(partnerId, messageMeta.created_at, isOwnMessage);
    }

    if (currentChatType.value === 'private' && currentChatId.value === partnerId) {
      const didUpdate = applyRecalledMessageToCurrentChat(eventPayload);
      if (!didUpdate && currentChatUser.value?.e2eeConversationId) {
        await loadE2EEConversationHistory(currentChatUser.value);
      }
      if (!isOwnMessage) {
        acknowledgeE2EEMessage(messageMeta.id, 'read');
      }
    } else if (contact && !isOwnMessage && !eventPayload.is_latest_message) {
      contact.unreadCount = contact.unreadCount || 0;
      acknowledgeE2EEMessage(messageMeta.id, 'delivered');
    } else if (!isOwnMessage) {
      acknowledgeE2EEMessage(messageMeta.id, 'delivered');
    }
    return;
  }

  if (eventPayload.chat_type === 'group') {
    const isOwnMessage = Number(messageMeta.sender_user_id) === Number(myUserId);
    upsertE2EEGroupConversationContact({
      id: eventPayload.conversation_id,
      group_id: eventPayload.group_id,
      username: eventPayload.group_name,
      avatar: eventPayload.group_avatar || '',
      protocol_version: messageMeta.protocol_version,
      last_message_is_recalled: Boolean(eventPayload.is_latest_message),
      last_message_sender_user_id: messageMeta.sender_user_id,
      last_message_sender_username: messageMeta.username,
      last_message_created_at: messageMeta.created_at,
      last_message_at: messageMeta.created_at,
    });

    if (eventPayload.is_latest_message) {
      updateGroupConversationRecallPreview(eventPayload.group_id, messageMeta.created_at, messageMeta.username, isOwnMessage);
    }

    if (currentChatType.value === 'group' && currentChatId.value === eventPayload.group_id) {
      const didUpdate = applyRecalledMessageToCurrentChat(eventPayload);
      if (!didUpdate && currentChatUser.value?.e2eeConversationId) {
        await loadE2EEConversationHistory(currentChatUser.value);
      }
      if (!isOwnMessage) {
        acknowledgeE2EEMessage(messageMeta.id, 'read');
      }
    } else if (!isOwnMessage) {
      acknowledgeE2EEMessage(messageMeta.id, 'delivered');
    }
  }
};

const applyGroupE2EEMessage = async (eventPayload) => {
  if (eventPayload.message?.is_recalled) {
    await applyMessageRecalledEvent(eventPayload);
    return;
  }

  if (!currentDeviceState.value) return;

  const targetPayload = (eventPayload.payloads || []).find((item) => item.recipient_device_id === currentDeviceId.value);
  if (!targetPayload) return;

  const contact = upsertE2EEGroupConversationContact({
    id: eventPayload.conversation_id,
    group_id: eventPayload.group_id,
    username: eventPayload.group_name,
    avatar: eventPayload.group_avatar || '',
    protocol_version: eventPayload.message.protocol_version,
  });

  if (eventPayload.message.message_type === 'sender_key_distribution') {
    try {
      const decrypted = await decryptIncomingEnvelope({
        scopeKey: getSessionStorageScope(),
        deviceState: currentDeviceState.value,
        envelope: parseEnvelopePayload(targetPayload.envelope),
        metadata: {sender_user_id: eventPayload.message.sender_user_id},
      });
      await saveGroupSenderKeyFromDistribution(parseSenderKeyDistributionPayload(decrypted.plaintext));
    } catch (distError) {
      console.error('[E2EE] Failed to decrypt sender key distribution from',
        eventPayload.message.sender_user_id, ':', distError,
        'sender_device_id:', eventPayload.message.sender_device_id,
        'envelope_type:', targetPayload.envelope_type);
      // Clear potentially corrupted session so next prekey message can rebuild cleanly
      const brokenEnvelope = parseEnvelopePayload(targetPayload.envelope);
      if (brokenEnvelope?.sender_device_id) {
        await clearStoredSessionState(getSessionStorageScope(), brokenEnvelope.sender_device_id);
      }
      // Request fresh sender keys via fallback mechanism
      requestGroupSenderKeysFromMembers(eventPayload.group_id).catch(console.error);
    }
    if (eventPayload.message.sender_user_id !== myUserId) {
      acknowledgeE2EEMessage(eventPayload.message.id, currentChatType.value === 'group' && currentChatId.value === eventPayload.group_id ? 'read' : 'delivered');
    }
    if (currentChatType.value === 'group' && currentChatId.value === eventPayload.group_id) {
      await loadE2EEConversationHistory(contact);
    }
    return;
  }

  const groupEnvelope = parseEnvelopePayload(targetPayload.envelope);
  const senderKeyState = await loadGroupSenderKey({
    scopeKey: getSessionStorageScope(),
    groupId: eventPayload.group_id,
    epoch: groupEnvelope.epoch,
    senderDeviceId: eventPayload.message.sender_device_id || groupEnvelope.sender_device_id,
  });
  if (!senderKeyState) {
    requestGroupSenderKeysFromMembers(eventPayload.group_id).catch(console.error);
    return;
  }

  let plaintext = '';
  try {
    plaintext = await decryptGroupSenderKeyMessage({
      senderKeyBase64: senderKeyState.senderKeyBase64,
      envelope: groupEnvelope,
    });
  } catch (groupDecryptError) {
    console.error('[E2EE] Failed to decrypt group message:', groupDecryptError,
      'group_id:', eventPayload.group_id, 'sender:', eventPayload.message.sender_user_id);
    plaintext = '[解密失败]';
  }

  if (plaintext && plaintext !== '[解密失败]') {
    getCacheEncryptionKey().then((ck) => {
      if (ck) saveCachedPlaintext(getSessionStorageScope(), eventPayload.message.id, plaintext, ck).catch(console.error);
    });
  }

  const isOwnMessage = eventPayload.message.sender_user_id === myUserId;
  if (isOwnMessage && eventPayload.message.client_message_id) {
    await removeOutboxMessage(getSessionStorageScope(), eventPayload.message.client_message_id);
    const acceptedStatus = getAcceptedOwnDeliveryStatus(eventPayload.message.id);
    deliveryStatusCache[eventPayload.message.id] = acceptedStatus;
    messageReceiptCache[eventPayload.message.id] = messageReceiptCache[eventPayload.message.id] || normalizeReceiptSummary(null, acceptedStatus);
  }

  updateGroupConversationPreview(
    eventPayload.group_id,
    plaintext,
    eventPayload.message.created_at,
    eventPayload.message.username,
    isOwnMessage,
    eventPayload.message.message_type,
  );

  const isCurrentChat = currentChatType.value === 'group' && currentChatId.value === eventPayload.group_id;
  if (isCurrentChat) {
    const existingIndex = messages.value.findIndex((message) => {
      return message.id === eventPayload.message.id || message.clientMessageId === eventPayload.message.client_message_id;
    });
    const nextMessage = {
      id: eventPayload.message.id,
      clientMessageId: eventPayload.message.client_message_id,
      from: eventPayload.message.sender_user_id,
      content: plaintext,
      msg_type: eventPayload.message.message_type,
      username: eventPayload.message.username,
      avatar: eventPayload.message.avatar || '',
      timestamp: eventPayload.message.created_at || null,
      isE2EE: true,
      protocolVersion: eventPayload.message.protocol_version || 'e2ee_v1',
      deliveryStatus: deliveryStatusCache[eventPayload.message.id] || 'sent',
      receiptSummary: messageReceiptCache[eventPayload.message.id] || (isOwnMessage ? normalizeReceiptSummary(null, 'sent') : null),
      isLocalOnly: false,
    };
    if (existingIndex >= 0) {
      messages.value[existingIndex] = {
        ...messages.value[existingIndex],
        ...nextMessage,
      };
    } else {
      messages.value.push(nextMessage);
      scrollToBottom();
    }

    if (['image', 'file'].includes(eventPayload.message.message_type)) {
      const descriptor = parseEncryptedAttachmentDescriptor(plaintext);
      if (descriptor) {
        loadEncryptedAttachmentUrl(descriptor).catch(console.error);
      }
    }
    if (!isOwnMessage) {
      acknowledgeE2EEMessage(eventPayload.message.id, 'read');
    }
  } else if (!isOwnMessage) {
    contact.unreadCount = (contact.unreadCount || 0) + 1;
    acknowledgeE2EEMessage(eventPayload.message.id, 'delivered');
  }
};

const loadE2EEConversationHistory = async (contact) => {
  const response = await axios.get(`${API_BASE}/e2ee/conversations/${contact.e2eeConversationId}/messages`, {
    headers: {Authorization: `Bearer ${token}`}
  });
  
  const rawMessages = response.data || [];
  let decryptedMessages = contact.type === 'group'
    ? await decryptGroupHistoryMessages(rawMessages, contact)
    : await decryptE2EEMessageList(rawMessages);
  decryptedMessages = await mergeConversationOutboxMessages(decryptedMessages, contact);
  messages.value = decryptedMessages;

  if (contact.type === 'private') {
    const latest = decryptedMessages[decryptedMessages.length - 1];
    if (latest) {
      if (isMessageRecalled(latest)) {
        updatePrivateConversationRecallPreview(contact.id, latest.timestamp, latest.from === myUserId, {bumpConversation: false});
      } else {
        updatePrivateConversationPreview(contact.id, latest.content, latest.timestamp, latest.from === myUserId, latest.msg_type, {bumpConversation: false});
      }
    }
  }

  const unreadIncoming = decryptedMessages.filter((message) => message.from !== myUserId).map((message) => message.id);
  unreadIncoming.forEach((messageId) => acknowledgeE2EEMessage(messageId, 'read'));
};

const syncE2EEInbox = async () => {
  if ((!sessionFeatureFlags.e2ee_private_enabled && !sessionFeatureFlags.e2ee_group_enabled) || !currentDeviceState.value) return;

  const response = await axios.get(`${API_BASE}/e2ee/inbox`, {
    headers: {Authorization: `Bearer ${token}`}
  });
  
  const items = response.data || [];
  
  for (const item of items) {
    const eventPayload = {
      type: 'message.new',
      chat_type: item.chat_type,
      conversation_id: item.conversation_id,
      partner_id: item.partner_id,
      group_id: item.group_id,
      group_name: item.group_name,
      group_avatar: item.group_avatar,
      message: {
        id: item.message_id,
        sender_user_id: item.sender_user_id,
        sender_device_id: item.sender_device_id,
        client_message_id: item.client_message_id,
        message_type: item.message_type,
        protocol_version: item.protocol_version,
        created_at: item.created_at,
        username: item.username,
        avatar: item.avatar,
        is_recalled: item.is_recalled === true,
        recalled_at: item.recalled_at || null,
        recalled_by_user_id: item.recalled_by_user_id || null,
      },
      payloads: [{
        recipient_device_id: currentDeviceId.value,
        envelope_type: item.envelope_type,
        envelope: item.envelope,
      }],
    };

    try {
      if (item.chat_type === 'group') {
        if (!sessionFeatureFlags.e2ee_group_enabled) {
          continue;
        }
        await applyGroupE2EEMessage(eventPayload);
      } else {
        if (!sessionFeatureFlags.e2ee_private_enabled) {
          continue;
        }
        await applyPrivateE2EEMessage(eventPayload);
      }
    } catch (error) {
      console.error('Failed to process inbox item', item, error);
    }
  }
};

const clearSocketReconnectTimer = () => {
  if (socketReconnectTimer) {
    window.clearTimeout(socketReconnectTimer);
    socketReconnectTimer = null;
  }
};

const scheduleSocketReconnect = () => {
  if (chatViewUnmounted || !(sessionFeatureFlags.e2ee_private_enabled || sessionFeatureFlags.e2ee_group_enabled) || !token) {
    return;
  }
  if (socketReconnectTimer || socketConnectPromise || isSocketReady()) {
    return;
  }

  const delay = Math.min(1000 * (2 ** socketReconnectAttempts), 10000);
  socketReconnectAttempts += 1;
  socketReconnectTimer = window.setTimeout(() => {
    socketReconnectTimer = null;
    ensureRealtimeSocketConnected().catch(console.error);
  }, delay);
};

const ensureRealtimeSocketConnected = async () => {
  if (!(sessionFeatureFlags.e2ee_private_enabled || sessionFeatureFlags.e2ee_group_enabled)) {
    return false;
  }
  if (isSocketReady()) {
    return true;
  }
  if (socketConnectPromise) {
    return await socketConnectPromise;
  }

  clearSocketReconnectTimer();
  socketConnectPromise = (async () => {
    try {
      await initWebSocket();
      socketReconnectAttempts = 0;
      await syncE2EEInbox();
      return true;
    } catch (error) {
      console.error('Failed to establish realtime connection:', error);
      scheduleSocketReconnect();
      return false;
    } finally {
      socketConnectPromise = null;
    }
  })();

  return await socketConnectPromise;
};

const finishChatStartup = async () => {
  if (startupInitialized) {
    return;
  }
  try {
    await Promise.all([loadContacts(), loadFriendData(), loadGroupAccessData()]);
    refreshAllTemporaryPrivateContactAccess();
    await ensureRealtimeSocketConnected();
    startupInitialized = true;
  } catch (e) {
    startupInitialized = false;
    throw e;
  }
};

// 生命周期。
onMounted(async () => {
  chatViewUnmounted = false;
  window.addEventListener('auth:changed', handleAuthChanged);
  try {
    if (!token) {
      await ensureAccessToken();
    }
    syncProfileFromAuthPayload();

    const meRes = await axios.get(`${API_BASE}/user/me`, {
      headers: {Authorization: `Bearer ${token}`}
    });
    syncProfileFromAuthPayload(meRes.data);
  } catch (e) {
    console.error(e);
    return router.push('/');
  }

  if (sessionFeatureFlags.e2ee_private_enabled || sessionFeatureFlags.e2ee_group_enabled) {
    try {
      await ensureDeviceBootstrap();
    } catch (e) {
      console.error(e);
      ElMessage.error(translateError(e.response?.data?.detail) || e.message || 'Failed to register device');
      return;
    }
  }

  try {
    await finishChatStartup();
  } catch (e) {
    console.error(e);
    ElMessage.error(translateError(e.response?.data?.detail) || 'Failed to initialize chat');
  }
});

onUnmounted(() => {
  chatViewUnmounted = true;
  clearSocketReconnectTimer();
  if (socket) socket.close();
  stopSafetyScan();
  startupInitialized = false;
  window.removeEventListener('auth:changed', handleAuthChanged);
  if (searchTimer) clearTimeout(searchTimer);
  if (createGroupSearchTimer) clearTimeout(createGroupSearchTimer);
  if (inviteSearchTimer) clearTimeout(inviteSearchTimer);
  searchAbortController?.abort();
  userLoadMoreAbortController?.abort();
  groupLoadMoreAbortController?.abort();
  createGroupSearchAbortController?.abort();
  inviteSearchAbortController?.abort();
  inviteAccessAbortController?.abort();
  searchAbortController = null;
  userLoadMoreAbortController = null;
  groupLoadMoreAbortController = null;
  createGroupSearchAbortController = null;
  inviteSearchAbortController = null;
  inviteAccessAbortController = null;
  clearPendingAvatarSelection('profile');
  clearPendingAvatarSelection('group');
  if (currentCropImageUrl.value) {
    URL.revokeObjectURL(currentCropImageUrl.value);
    currentCropImageUrl.value = '';
  }
  Object.values(attachmentObjectUrls).forEach((url) => {
    if (url) URL.revokeObjectURL(url);
  });
});

// 数据加载。
const loadFriendData = async () => {
  friendRequestsLoading.value = true;
  try {
    const [requestsRes, friendsRes] = await Promise.all([
      axios.get(`${API_BASE}/user/friends/requests`, {
        headers: {Authorization: `Bearer ${token}`}
      }),
      axios.get(`${API_BASE}/user/friends`, {
        headers: {Authorization: `Bearer ${token}`}
      })
    ]);

    incomingFriendRequests.value = requestsRes.data.incoming || [];
    outgoingFriendRequests.value = requestsRes.data.outgoing || [];
    friendsList.value = friendsRes.data || [];
    refreshAllTemporaryPrivateContactAccess();
  } catch (e) {
    incomingFriendRequests.value = [];
    outgoingFriendRequests.value = [];
    friendsList.value = [];
    console.error(e);
  } finally {
    friendRequestsLoading.value = false;
  }
};

const openNotificationCenter = async (preferredTab = null, preferredNestedTab = null) => {
  notificationCenterVisible.value = true;
  await Promise.all([loadFriendData(), loadGroupAccessData()]);

  if (preferredTab === 'friends') {
    notificationCenterTab.value = 'friends';
    friendRequestsTab.value = preferredNestedTab || 'incoming';
    return;
  }

  if (preferredTab === 'groups') {
    notificationCenterTab.value = 'groups';
    groupAccessTab.value = preferredNestedTab || 'invites';
    return;
  }

  if (incomingFriendRequests.value.length > 0) {
    notificationCenterTab.value = 'friends';
    friendRequestsTab.value = 'incoming';
  } else if (receivedGroupInvites.value.length > 0) {
    notificationCenterTab.value = 'groups';
    groupAccessTab.value = 'invites';
  } else if (ownedGroupJoinRequests.value.length > 0) {
    notificationCenterTab.value = 'groups';
    groupAccessTab.value = 'owned';
  } else if (myGroupJoinRequests.value.length > 0) {
    notificationCenterTab.value = 'groups';
    groupAccessTab.value = 'requests';
  } else if (outgoingFriendRequests.value.length > 0) {
    notificationCenterTab.value = 'friends';
    friendRequestsTab.value = 'outgoing';
  } else if (friendsList.value.length > 0) {
    notificationCenterTab.value = 'friends';
    friendRequestsTab.value = 'friends-list';
  }
};

const loadGroupAccessData = async () => {
  groupAccessLoading.value = true;
  try {
    groupAccessError.value = '';
    const [invitesRes, requestsRes, ownedRequestsRes] = await Promise.all([
      axios.get(`${API_BASE}/chat/group/invites`, {
        headers: {Authorization: `Bearer ${token}`}
      }),
      axios.get(`${API_BASE}/chat/group/join-requests/mine`, {
        headers: {Authorization: `Bearer ${token}`}
      }),
      axios.get(`${API_BASE}/chat/group/join-requests/owned`, {
        headers: {Authorization: `Bearer ${token}`}
      })
    ]);

    receivedGroupInvites.value = invitesRes.data.items || [];
    myGroupJoinRequests.value = requestsRes.data.items || [];
    ownedGroupJoinRequests.value = ownedRequestsRes.data.items || [];
  } catch (e) {
    receivedGroupInvites.value = [];
    myGroupJoinRequests.value = [];
    ownedGroupJoinRequests.value = [];
    groupAccessError.value = t('searchFailed');
    console.error(e);
  } finally {
    groupAccessLoading.value = false;
  }
};

const loadCurrentGroupInvites = async (groupId) => {
  inviteAccessAbortController?.abort();
  const controller = new AbortController();
  inviteAccessAbortController = controller;
  const requestId = ++inviteAccessRequestId;
  inviteAccessLoading.value = true;
  try {
    const res = await axios.get(`${API_BASE}/chat/group/${groupId}/invites`, {
      headers: {Authorization: `Bearer ${token}`},
      signal: controller.signal
    });

    if (requestId !== inviteAccessRequestId) return;
    currentGroupInvites.value = res.data.items || [];
  } catch (e) {
    if (e.code === 'ERR_CANCELED') return;
    console.error(e);
    if (requestId === inviteAccessRequestId) {
      currentGroupInvites.value = [];
    }
  } finally {
    if (requestId === inviteAccessRequestId) {
      if (inviteAccessAbortController === controller) {
        inviteAccessAbortController = null;
      }
      inviteAccessLoading.value = false;
    }
  }
};

const loadAllUsers = async () => {
  try {
    const res = await axios.get(`${API_BASE}/user/friends`, {
      headers: {Authorization: `Bearer ${token}`}
    });
    allUsers.value = res.data;
    syncTemporaryPrivateContacts(res.data);
  } catch (e) {
    console.error(e);
  }
};

const fetchUserSearchResults = async (keyword, requestType, options = {}) => {
  const {append = false} = options;
  let shouldCheckAutoLoad = false;

  if (requestType === 'create') {
    createGroupSearchAbortController?.abort();
  } else {
    inviteSearchAbortController?.abort();
  }

  const controller = new AbortController();
  if (requestType === 'create') {
    createGroupSearchAbortController = controller;
    if (!append) {
      createGroupSearchLoading.value = true;
      createGroupSearchError.value = '';
    } else {
      createGroupSearchLoadingMore.value = true;
    }
  } else {
    inviteSearchAbortController = controller;
    if (!append) {
      inviteSearchLoading.value = true;
      inviteSearchError.value = '';
    } else {
      inviteSearchLoadingMore.value = true;
    }
  }

  const requestId = requestType === 'create'
    ? ++createGroupSearchRequestId
    : ++inviteSearchRequestId;
  const offset = append
    ? (requestType === 'create' ? createGroupSearchNextOffset.value : inviteSearchNextOffset.value)
    : 0;

  try {
    const endpoint = requestType === 'create' || requestType === 'invite'
      ? `${API_BASE}/user/friends/search`
      : `${API_BASE}/user/search`;
    const res = await axios.get(endpoint, {
      params: {q: keyword, limit: 30, offset},
      headers: {Authorization: `Bearer ${token}`},
      signal: controller.signal
    });

    const items = res.data.items || [];

    if (requestType === 'create') {
      if (requestId !== createGroupSearchRequestId) return;
      createGroupSearchResults.value = append ? mergeUniqueById(createGroupSearchResults.value, items) : items;
      createGroupSearchHasMore.value = Boolean(res.data.has_more);
      createGroupSearchNextOffset.value = res.data.next_offset || 0;
    } else {
      if (requestId !== inviteSearchRequestId) return;
      inviteSearchResults.value = append ? mergeUniqueById(inviteSearchResults.value, items) : items;
      inviteSearchHasMore.value = Boolean(res.data.has_more);
      inviteSearchNextOffset.value = res.data.next_offset || 0;
    }

    syncTemporaryPrivateContacts(items);
    shouldCheckAutoLoad = true;
  } catch (e) {
    if (e.code === 'ERR_CANCELED') return;
    if (requestType === 'create') {
      if (requestId !== createGroupSearchRequestId) return;
      if (!append) {
        createGroupSearchResults.value = [];
        createGroupSearchHasMore.value = false;
        createGroupSearchNextOffset.value = 0;
        createGroupSearchError.value = e.response?.status === 429 ? t('searchRateLimited') : t('searchFailed');
      } else {
        ElMessage.error(e.response?.status === 429 ? t('searchRateLimited') : t('searchFailed'));
      }
    } else {
      if (requestId !== inviteSearchRequestId) return;
      if (!append) {
        inviteSearchResults.value = [];
        inviteSearchHasMore.value = false;
        inviteSearchNextOffset.value = 0;
        inviteSearchError.value = e.response?.status === 429 ? t('searchRateLimited') : t('searchFailed');
      } else {
        ElMessage.error(e.response?.status === 429 ? t('searchRateLimited') : t('searchFailed'));
      }
    }
    console.error(e);
  } finally {
    if (requestType === 'create') {
      if (requestId === createGroupSearchRequestId) {
        if (createGroupSearchAbortController === controller) {
          createGroupSearchAbortController = null;
        }
        createGroupSearchLoading.value = false;
        createGroupSearchLoadingMore.value = false;
        if (shouldCheckAutoLoad) {
          await maybeAutoLoadPicker(requestType);
        }
      }
    } else if (requestId === inviteSearchRequestId) {
      if (inviteSearchAbortController === controller) {
        inviteSearchAbortController = null;
      }
      inviteSearchLoading.value = false;
      inviteSearchLoadingMore.value = false;
      if (shouldCheckAutoLoad) {
        await maybeAutoLoadPicker(requestType);
      }
    }
  }
};

const performSearch = async (keyword) => {
  searchAbortController?.abort();
  const controller = new AbortController();
  searchAbortController = controller;
  const requestId = ++latestSearchId;
  searchResults.loading = true;
  let shouldCheckAutoLoad = false;

  try {
    searchResults.error = '';
    const [usersRes, groupsRes] = await Promise.all([
      axios.get(`${API_BASE}/user/search`, {
        params: {q: keyword, limit: 12, offset: 0},
        headers: {Authorization: `Bearer ${token}`},
        signal: controller.signal
      }),
      axios.get(`${API_BASE}/chat/group/search`, {
        params: {q: keyword, limit: 12, offset: 0},
        headers: {Authorization: `Bearer ${token}`},
        signal: controller.signal
      })
    ]);

    if (requestId !== latestSearchId) return;

    searchResults.users = mergeUniqueById([], usersRes.data.items || []);
    searchResults.groups = mergeUniqueById([], groupsRes.data.items || []);
    searchResults.usersHasMore = Boolean(usersRes.data.has_more);
    searchResults.groupsHasMore = Boolean(groupsRes.data.has_more);
    searchResults.usersNextOffset = usersRes.data.next_offset || 0;
    searchResults.groupsNextOffset = groupsRes.data.next_offset || 0;
    searchResults.groupsAnchorTs = groupsRes.data.anchor_ts || null;
    syncTemporaryPrivateContacts(searchResults.users);
    shouldCheckAutoLoad = true;
  } catch (e) {
    if (e.code === 'ERR_CANCELED') return;
    if (requestId !== latestSearchId) return;
    searchResults.users = [];
    searchResults.groups = [];
    searchResults.error = e.response?.status === 429 ? t('searchRateLimited') : t('searchFailed');
    console.error(e);
  } finally {
    if (requestId === latestSearchId) {
      if (searchAbortController === controller) {
        searchAbortController = null;
      }
      searchResults.loading = false;
      if (shouldCheckAutoLoad) {
        await maybeAutoLoadMainSearch();
      }
    }
  }
};

const loadMoreSearchResults = async (section) => {
  const keyword = searchText.value.trim();
  if (!keyword) return;
  const activeSearchId = latestSearchId;
  let shouldCheckAutoLoad = false;

  const isUserSection = section === 'users';
  const isLoadingMore = isUserSection ? searchResults.usersLoadingMore : searchResults.groupsLoadingMore;
  const hasMore = isUserSection ? searchResults.usersHasMore : searchResults.groupsHasMore;
  const nextOffset = isUserSection ? searchResults.usersNextOffset : searchResults.groupsNextOffset;

  if (isLoadingMore || !hasMore) return;

  if (isUserSection) {
    userLoadMoreAbortController?.abort();
    searchResults.usersPaginationTouched = true;
    searchResults.usersLoadingMore = true;
  } else {
    groupLoadMoreAbortController?.abort();
    searchResults.groupsPaginationTouched = true;
    searchResults.groupsLoadingMore = true;
  }

  const controller = new AbortController();
  if (isUserSection) {
    userLoadMoreAbortController = controller;
  } else {
    groupLoadMoreAbortController = controller;
  }

  try {
    const endpoint = isUserSection ? `${API_BASE}/user/search` : `${API_BASE}/chat/group/search`;
    const params = {q: keyword, limit: 12, offset: nextOffset};
    if (!isUserSection && searchResults.groupsAnchorTs) {
      params.anchor_ts = searchResults.groupsAnchorTs;
    }

    const res = await axios.get(endpoint, {
      params,
      headers: {Authorization: `Bearer ${token}`},
      signal: controller.signal
    });

    const items = res.data.items || [];
    if (keyword !== searchText.value.trim() || activeSearchId !== latestSearchId) return;

    if (isUserSection) {
      searchResults.users = mergeUniqueById(searchResults.users, items);
      searchResults.usersHasMore = Boolean(res.data.has_more);
      searchResults.usersNextOffset = res.data.next_offset || 0;
      syncTemporaryPrivateContacts(searchResults.users);
    } else {
      searchResults.groups = mergeUniqueById(searchResults.groups, items);
      searchResults.groupsHasMore = Boolean(res.data.has_more);
      searchResults.groupsNextOffset = res.data.next_offset || 0;
    }
    shouldCheckAutoLoad = true;
  } catch (e) {
    if (e.code === 'ERR_CANCELED') return;
    if (keyword !== searchText.value.trim() || activeSearchId !== latestSearchId) return;
    const message = e.response?.status === 429 ? t('searchRateLimited') : t('searchFailed');
    ElMessage.error(message);
  } finally {
    if (keyword !== searchText.value.trim() || activeSearchId !== latestSearchId) return;

    if (isUserSection) {
      if (userLoadMoreAbortController === controller) {
        userLoadMoreAbortController = null;
      }
    } else if (groupLoadMoreAbortController === controller) {
      groupLoadMoreAbortController = null;
    }

    if (isUserSection) {
      searchResults.usersLoadingMore = false;
    } else {
      searchResults.groupsLoadingMore = false;
    }

    if (shouldCheckAutoLoad) {
      await maybeAutoLoadMainSearch();
    }
  }
};

const loadMorePickerSearchResults = async (requestType) => {
  const keyword = requestType === 'create'
    ? createGroupMemberSearch.value.trim()
    : inviteSearch.value.trim();

  if (!keyword) return;

  const isCreate = requestType === 'create';
  if (isCreate) {
    if (createGroupSearchLoadingMore.value || !createGroupSearchHasMore.value) return;
    createGroupSearchPaginationTouched.value = true;
  } else if (inviteSearchLoadingMore.value || !inviteSearchHasMore.value) {
    return;
  } else {
    inviteSearchPaginationTouched.value = true;
  }

  await fetchUserSearchResults(keyword, requestType, {append: true});
};

const isNearBottom = (element, threshold = 80) => {
  if (!element) return false;
  return element.scrollTop + element.clientHeight >= element.scrollHeight - threshold;
};

const getScrollElementByKind = (kind) => {
  if (kind === 'main') return contactListRef.value;
  if (kind === 'create') return createGroupListRef.value;
  if (kind === 'invite') return inviteListRef.value;
  return null;
};

const resetScrollPosition = async (kind) => {
  await nextTick();
  const element = getScrollElementByKind(kind);
  if (element) {
    element.scrollTop = 0;
  }
  resetScrollUi(kind);
};

const resetScrollUi = (kind) => {
  scrollUi[kind].showBackToTop = false;
  scrollUi[kind].reachedEnd = false;
};

const updateScrollUi = async (kind) => {
  await nextTick();

  const element = getScrollElementByKind(kind);
  if (!element) {
    resetScrollUi(kind);
    return;
  }

  scrollUi[kind].showBackToTop = element.scrollTop > 140;

  if (kind === 'main') {
    const hasSections = searchMatchedChats.value.length > 0 || discoveredUsers.value.length > 0 || searchGroupEntries.value.length > 0;
    scrollUi[kind].reachedEnd = showSearchResults.value &&
      hasSections &&
      isNearBottom(element, 24) &&
      !searchResults.loading &&
      !searchResults.usersLoadingMore &&
      !searchResults.groupsLoadingMore &&
      !searchResults.usersHasMore &&
      !searchResults.groupsHasMore &&
      (searchResults.usersPaginationTouched || searchResults.groupsPaginationTouched);
    return;
  }

  if (kind === 'create') {
    scrollUi[kind].reachedEnd = createGroupVisible.value &&
      Boolean(createGroupMemberSearch.value.trim()) &&
      filteredCreateGroupCandidates.value.length > 0 &&
      isNearBottom(element, 24) &&
      !createGroupSearchLoading.value &&
      !createGroupSearchLoadingMore.value &&
      !createGroupSearchHasMore.value &&
      createGroupSearchPaginationTouched.value;
    return;
  }

  scrollUi[kind].reachedEnd = inviteVisible.value &&
    Boolean(inviteSearch.value.trim()) &&
    filteredAvailableContacts.value.length > 0 &&
    isNearBottom(element, 24) &&
    !inviteSearchLoading.value &&
    !inviteSearchLoadingMore.value &&
    !inviteSearchHasMore.value &&
    inviteSearchPaginationTouched.value;
};

const scrollListToTop = async (kind) => {
  const element = getScrollElementByKind(kind);
  if (!element) return;
  element.scrollTo({top: 0, behavior: 'smooth'});
  await nextTick();
  updateScrollUi(kind);
};

const maybeAutoLoadMainSearch = async () => {
  await nextTick();
  const element = contactListRef.value;
  if (!showSearchResults.value || !element) {
    resetScrollUi('main');
    return;
  }

  if (element.scrollHeight <= element.clientHeight + 20) {
    if (searchResults.usersHasMore && !searchResults.usersLoadingMore) {
      await loadMoreSearchResults('users');
    } else if (searchResults.groupsHasMore && !searchResults.groupsLoadingMore) {
      await loadMoreSearchResults('groups');
    }
  }

  await updateScrollUi('main');
};

const maybeAutoLoadPicker = async (requestType) => {
  await nextTick();
  const isCreate = requestType === 'create';
  const element = isCreate ? createGroupListRef.value : inviteListRef.value;
  const hasMore = isCreate ? createGroupSearchHasMore.value : inviteSearchHasMore.value;
  const isLoadingMore = isCreate ? createGroupSearchLoadingMore.value : inviteSearchLoadingMore.value;
  const keyword = isCreate ? createGroupMemberSearch.value.trim() : inviteSearch.value.trim();

  if (!element || !keyword || !hasMore || isLoadingMore) {
    await updateScrollUi(isCreate ? 'create' : 'invite');
    return;
  }

  if (element.scrollHeight <= element.clientHeight + 20) {
    await loadMorePickerSearchResults(requestType);
  }

  await updateScrollUi(isCreate ? 'create' : 'invite');
};

const handleMainSearchScroll = async () => {
  if (!showSearchResults.value) {
    resetScrollUi('main');
    return;
  }

  await updateScrollUi('main');
  if (!isNearBottom(contactListRef.value)) return;

  if (searchResults.usersHasMore && !searchResults.usersLoadingMore) {
    await loadMoreSearchResults('users');
  }

  if (searchResults.groupsHasMore && !searchResults.groupsLoadingMore) {
    await loadMoreSearchResults('groups');
  }
};

const handleCreateGroupScroll = async () => {
  await updateScrollUi('create');
  if (!createGroupMemberSearch.value.trim() || !isNearBottom(createGroupListRef.value)) return;
  await loadMorePickerSearchResults('create');
};

const handleInviteScroll = async () => {
  await updateScrollUi('invite');
  if (!inviteSearch.value.trim() || !isNearBottom(inviteListRef.value)) return;
  await loadMorePickerSearchResults('invite');
};

watch(searchText, (value) => {
  const keyword = value.trim();
  if (searchTimer) clearTimeout(searchTimer);

  if (!keyword) {
    searchAbortController?.abort();
    searchAbortController = null;
    latestSearchId += 1;
    resetMainSearchResults();
    return;
  }

  searchAbortController?.abort();
  searchAbortController = null;
  latestSearchId += 1;
  resetMainSearchResults();
  searchResults.loading = true;

  searchTimer = setTimeout(() => {
    performSearch(keyword);
  }, 250);
});

watch(createGroupMemberSearch, (value) => {
  const keyword = value.trim();
  if (createGroupSearchTimer) clearTimeout(createGroupSearchTimer);
  if (!keyword) {
    createGroupSearchAbortController?.abort();
    createGroupSearchAbortController = null;
    createGroupSearchRequestId += 1;
    createGroupSearchResults.value = [];
    createGroupSearchLoading.value = false;
    createGroupSearchLoadingMore.value = false;
    createGroupSearchError.value = '';
    createGroupSearchHasMore.value = false;
    createGroupSearchNextOffset.value = 0;
    createGroupSearchPaginationTouched.value = false;
    resetScrollPosition('create');
    return;
  }

  createGroupSearchAbortController?.abort();
  createGroupSearchAbortController = null;
  createGroupSearchRequestId += 1;
  createGroupSearchResults.value = [];
  createGroupSearchHasMore.value = false;
  createGroupSearchNextOffset.value = 0;
  createGroupSearchLoadingMore.value = false;
  createGroupSearchError.value = '';
  createGroupSearchPaginationTouched.value = false;
  createGroupSearchLoading.value = true;
  resetScrollPosition('create');

  createGroupSearchTimer = setTimeout(() => {
    fetchUserSearchResults(keyword, 'create');
  }, 200);
});

watch(inviteSearch, (value) => {
  const keyword = value.trim();
  if (inviteSearchTimer) clearTimeout(inviteSearchTimer);
  if (!keyword) {
    inviteSearchAbortController?.abort();
    inviteSearchAbortController = null;
    inviteSearchRequestId += 1;
    inviteSearchResults.value = [];
    inviteSearchLoading.value = false;
    inviteSearchLoadingMore.value = false;
    inviteSearchError.value = '';
    inviteSearchHasMore.value = false;
    inviteSearchNextOffset.value = 0;
    inviteSearchPaginationTouched.value = false;
    resetScrollPosition('invite');
    return;
  }

  inviteSearchAbortController?.abort();
  inviteSearchAbortController = null;
  inviteSearchRequestId += 1;
  inviteSearchResults.value = [];
  inviteSearchHasMore.value = false;
  inviteSearchNextOffset.value = 0;
  inviteSearchLoadingMore.value = false;
  inviteSearchError.value = '';
  inviteSearchPaginationTouched.value = false;
  inviteSearchLoading.value = true;
  resetScrollPosition('invite');

  inviteSearchTimer = setTimeout(() => {
    fetchUserSearchResults(keyword, 'invite');
  }, 200);
});

watch(inputText, (value) => {
  if (currentChatId.value === null) return;
  setDraftForConversation(currentChatId.value, currentChatType.value, value, {
    username: currentChatUser.value?.username || '',
    type: currentChatType.value,
    canChat: currentChatCanSend.value
  });
});

const loadContacts = async () => {
  try {
    if (!sessionFeatureFlags.e2ee_private_enabled && !sessionFeatureFlags.e2ee_group_enabled) {
      contactList.value = [];
      return;
    }

    const e2eeRes = await axios.get(`${API_BASE}/e2ee/conversations`, {
      headers: {Authorization: `Bearer ${token}`}
    });

    const unreadMap = new Map(
      contactList.value.map(contact => [`${contact.type}:${contact.id}`, contact.unreadCount || 0])
    );

    const serverContacts = [];
    (e2eeRes.data || []).forEach((conversationItem) => {
      if (conversationItem.type === 'group') {
        if (!sessionFeatureFlags.e2ee_group_enabled) {
          return;
        }
        const existingGroupContact = getMatchedConversationContact(
          contactList.value.find((item) => item.id === conversationItem.group_id && item.type === 'group'),
          conversationItem.id,
        );
        const previewEntry = getValidatedGroupPreviewEntry(conversationItem);
        const recalledPreview = conversationItem.last_message_is_recalled
          ? buildConversationRecallPreview({
            chatType: 'group',
            senderName: conversationItem.last_message_sender_username,
            isOwnMessage: Number(conversationItem.last_message_sender_user_id) === Number(myUserId),
          })
          : '';
        const previewTimestamp = conversationItem.last_message_created_at || conversationItem.last_message_at || previewEntry?.timestamp || existingGroupContact?.lastActivityAt || null;
        if (recalledPreview && previewTimestamp) {
          saveGroupPreviewEntry(myUserId, conversationItem.group_id, {
            text: recalledPreview,
            timestamp: previewTimestamp,
          }, getPreviewStorageScope());
        }
        serverContacts.unshift({
          id: conversationItem.group_id,
          username: conversationItem.username,
          avatar: conversationItem.avatar || '',
          type: 'group',
          lastMessage: recalledPreview || previewEntry?.text || existingGroupContact?.lastMessage || '',
          lastTime: previewTimestamp ? formatClockTime(previewTimestamp) : (existingGroupContact?.lastTime || ''),
          lastActivityAt: pickLatestTimestamp(existingGroupContact?.lastActivityAt, previewEntry?.timestamp, previewTimestamp, conversationItem.last_message_at),
          isOnline: true,
          canChat: true,
          protocolVersion: conversationItem.protocol_version,
          e2eeConversationId: conversationItem.id,
          unreadCount: unreadMap.get(`group:${conversationItem.group_id}`) || 0
        });
        return;
      }

      const existingPrivateContact = getMatchedConversationContact(
        contactList.value.find((item) => item.id === conversationItem.partner_id && item.type === 'private'),
        conversationItem.id,
      );
      const previewEntry = getValidatedPrivatePreviewEntry(conversationItem);
      const recalledPreview = conversationItem.last_message_is_recalled
        ? buildConversationRecallPreview({
          chatType: 'private',
          isOwnMessage: Number(conversationItem.last_message_sender_user_id) === Number(myUserId),
        })
        : '';
      const previewTimestamp = conversationItem.last_message_created_at || conversationItem.last_message_at || previewEntry?.timestamp || existingPrivateContact?.lastActivityAt || null;
      if (recalledPreview && previewTimestamp) {
        savePrivatePreviewEntry(myUserId, conversationItem.partner_id, {
          text: recalledPreview,
          timestamp: previewTimestamp,
        }, getPreviewStorageScope());
      }
      serverContacts.unshift({
        id: conversationItem.partner_id,
        username: conversationItem.username,
        avatar: conversationItem.avatar || '',
        type: 'private',
        lastMessage: recalledPreview || previewEntry?.text || existingPrivateContact?.lastMessage || '',
        lastTime: previewTimestamp
          ? formatClockTime(previewTimestamp)
          : (existingPrivateContact?.lastTime || ''),
        lastActivityAt: pickLatestTimestamp(existingPrivateContact?.lastActivityAt, previewEntry?.timestamp, previewTimestamp, conversationItem.last_message_at),
        isOnline: existingPrivateContact?.isOnline || false,
        canChat: conversationItem.can_chat !== false,
        protocolVersion: conversationItem.protocol_version,
        e2eeConversationId: conversationItem.id,
        unreadCount: unreadMap.get(`private:${conversationItem.partner_id}`) || 0
      });
    });
    const serverKeys = new Set(serverContacts.map(contact => `${contact.type}:${contact.id}`));

    const temporaryContacts = contactList.value
      .map((contact, index) => ({contact, index}))
      .filter(({contact}) => contact.isTemporary && !serverKeys.has(`${contact.type}:${contact.id}`));

    const temporaryKeys = new Set(temporaryContacts.map(({contact}) => `${contact.type}:${contact.id}`));
    const rehydratedDraftContacts = Object.entries(conversationDrafts.value)
      .map(([key, entry]) => ({key, entry: normalizeDraftEntry(entry)}))
      .filter(({key, entry}) => {
        return (
          key.startsWith('private:') &&
          Boolean(entry.text) &&
          !serverKeys.has(key) &&
          !temporaryKeys.has(key)
        );
      })
      .sort((left, right) => left.entry.updatedAt - right.entry.updatedAt)
      .map(({key, entry}) => {
        const [, rawId] = key.split(':');
        return {
          contact: {
            id: Number(rawId),
            username: entry.username || `ID ${rawId}`,
            type: 'private',
            lastMessage: '',
            lastTime: '',
            lastActivityAt: entry.updatedAt ? new Date(entry.updatedAt).toISOString() : null,
            isOnline: false,
            unreadCount: 0,
            isTemporary: true,
            canChat: entry.canChat
          },
          index: 0
        };
      });

    const mergedContacts = [...serverContacts];
    [...rehydratedDraftContacts, ...temporaryContacts].forEach(({contact, index}) => {
      const targetIndex = Math.min(index, mergedContacts.length);
      mergedContacts.splice(targetIndex, 0, contact);
    });

    contactList.value = sortContactsByActivity(mergedContacts);
    hydrateMissingGroupConversationPreviews(contactList.value).catch(console.error);

    rehydratedDraftContacts.forEach(({contact}) => {
      if (typeof contact.canChat !== 'boolean') {
        refreshTemporaryPrivateContactAccess(contact.id);
      }
    });

    if (currentChatId.value !== null && currentChatType.value === 'private' && !currentChatCanSend.value) {
      inputText.value = '';
    }

    Object.keys(conversationDrafts.value).forEach((key) => {
      if (!key.startsWith('group:')) return;
      if (serverKeys.has(key)) return;
      clearDraftForConversation(Number(key.split(':')[1]), 'group');
    });
  } catch (e) {
    console.error(e);
  }
};

const ensureConversationEntry = (entry) => {
  const index = contactList.value.findIndex(contact => {
    return contact.id === entry.id && contact.type === entry.type;
  });

  if (index === -1) {
    const conversation = {
      ...entry,
      protocolVersion: entry.protocolVersion || 'e2ee_v1',
      lastMessage: entry.lastMessage || '',
      lastTime: entry.lastTime || '',
      lastActivityAt: entry.lastActivityAt || null,
      unreadCount: entry.unreadCount || 0,
      isOnline: entry.isOnline || false,
      isTemporary: entry.isTemporary || false
    };
    contactList.value = [...contactList.value, conversation];
    if (conversation.lastActivityAt) {
      sortContactListByActivity();
    }
    return conversation;
  }

  contactList.value[index] = {
    ...contactList.value[index],
    ...entry
  };
  return contactList.value[index];
};

const removeInvalidGroupConversation = (groupId) => {
  clearDraftForConversation(groupId, 'group');
  contactList.value = contactList.value.filter(contact => {
    return !(contact.id === groupId && contact.type === 'group');
  });
  currentGroupAvatar.value = '';
  groupMembers.value = [];
  isGroupOwner.value = false;
  groupManageVisible.value = false;
  inviteVisible.value = false;
  clearPendingAvatarSelection('group');

  if (currentChatId.value === groupId && currentChatType.value === 'group') {
    currentChatId.value = null;
    currentChatType.value = 'private';
    messages.value = [];
    inputText.value = '';
  }
};

const closeTemporaryConversation = (contact) => {
  if (searchText.value) {
    searchText.value = '';
  }
  clearDraftForConversation(contact.id, contact.type);

  contactList.value = contactList.value.filter(existingContact => {
    return !(existingContact.id === contact.id && existingContact.type === contact.type && existingContact.isTemporary);
  });

  if (currentChatId.value === contact.id && currentChatType.value === contact.type) {
    currentChatId.value = null;
    currentChatType.value = 'private';
    messages.value = [];
    inputText.value = '';
  }
};

const selectChat = async (contact) => {
  const nextChatType = contact.type || 'private';
  const previousChatId = currentChatId.value;
  const previousChatType = currentChatType.value;
  const previousMessages = [...messages.value];
  const previousInput = inputText.value;
  try {
    if (searchText.value) {
      searchText.value = '';
    }
    currentChatId.value = contact.id;
    currentChatType.value = nextChatType;
    contact.unreadCount = 0;

    if (
      ((nextChatType === 'private' && sessionFeatureFlags.e2ee_private_enabled)
      || (nextChatType === 'group' && sessionFeatureFlags.e2ee_group_enabled))
      && contact.e2eeConversationId
    ) {
      await loadE2EEConversationHistory(contact);
    } else {
      messages.value = [];
    }

    inputText.value = getDraftForConversation(contact.id, nextChatType);
    scrollToBottom();
    return true;
  } catch (e) {
    if (contact.isTemporary && nextChatType === 'private') {
      searchText.value = '';
      currentChatId.value = contact.id;
      currentChatType.value = nextChatType;
      messages.value = [];
      inputText.value = getDraftForConversation(contact.id, nextChatType);
    }

    if (nextChatType === 'group' && e.response && [403, 404].includes(e.response.status)) {
      removeInvalidGroupConversation(contact.id);
      ElMessage.info(t('groupUnavailable'));
      console.error(e);
      return false;
    }
    currentChatId.value = previousChatId;
    currentChatType.value = previousChatType;
    messages.value = previousMessages;
    inputText.value = previousInput;
    ElMessage.error(translateError(e.response?.data?.detail) || 'Failed');
    console.error(e);
    return false;
  }
};

// WebSocket 通信。
const initWebSocket = async () => {
  const ticketRes = await axios.post(
    `${API_BASE}/e2ee/ws-ticket`,
    {},
    {headers: {Authorization: `Bearer ${token}`}}
  );
  const wsUrl = `${WS_ORIGIN}/api/e2ee/ws?ticket=${encodeURIComponent(ticketRes.data.ticket)}`;

  socket = new WebSocket(wsUrl);
  socket.onmessage = async (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'message.new') {
        if (data.chat_type === 'group') {
          if (!sessionFeatureFlags.e2ee_group_enabled) {
            return;
          }
          await applyGroupE2EEMessage(data);
        } else {
          if (!sessionFeatureFlags.e2ee_private_enabled) {
            return;
          }
          await applyPrivateE2EEMessage(data);
        }
      } else if (data.type === 'presence.snapshot') {
        applyPresenceSnapshot(data.online_user_ids || []);
      } else if (data.type === 'user_status') {
        applyPresenceStatus(data.user_id, data.status === 'online');
      } else if (data.type === 'group_created') {
        await loadContacts();
        await refreshSearchResultsIfNeeded();

        if (currentChatType.value === 'group' && !hasConversation(currentChatId.value, 'group')) {
          removeInvalidGroupConversation(currentChatId.value);
          ElMessage.info(t('groupUnavailable'));
          return;
        }

        // 管理窗口打开时同步刷新成员列表。
        if (
          groupManageVisible.value &&
          currentChatType.value === 'group' &&
          currentChatId.value === data.group_id
        ) {
          await fetchGroupMembers();
        }
      } else if (data.type === 'group_access_updated') {
        await loadGroupAccessData();
        await refreshSearchResultsIfNeeded();
        delete groupDeviceDirectory[data.group_id];

        if (inviteVisible.value && currentChatType.value === 'group' && currentChatId.value === data.group_id) {
          await loadCurrentGroupInvites(data.group_id);
        }
      } else if (data.type === 'group_epoch_changed') {
        delete groupDeviceDirectory[data.group_id];
        await loadContacts();
        if (sessionFeatureFlags.e2ee_group_enabled) {
          redistributeSenderKeysToGroupMembers(data.group_id).catch(console.error);
        }
        if (currentChatType.value === 'group' && currentChatId.value === data.group_id && currentChatUser.value?.e2eeConversationId) {
          await loadE2EEConversationHistory(currentChatUser.value);
        }
      } else if (data.type === 'sender_key_request_response') {
        if (sessionFeatureFlags.e2ee_group_enabled) {
          const groupId = data.group_id;
          const requesterUserId = data.requester_user_id;
          if (groupId && requesterUserId && isSocketReady()) {
            redistributeSenderKeyToMember(groupId, requesterUserId).catch(console.error);
          }
        }
      } else if (data.type === 'friend_access_updated') {
        await loadContacts();
        await loadFriendData();
        await refreshSearchResultsIfNeeded();

        if (createGroupVisible.value || inviteVisible.value) {
          await loadAllUsers();
        }

        if (data.peer_id) {
          await refreshTemporaryPrivateContactAccess(data.peer_id);
        }

        if (currentChatType.value === 'private' && currentChatId.value === data.peer_id && !currentChatCanSend.value) {
          ElMessage.info(t('privateChatLocked'));
        }
      } else if (data.type === 'message.recalled') {
        await applyMessageRecalledEvent(data);
      } else if (data.type === 'user_updated') {
        if (data.user_id !== myUserId || myUsername.value !== data.username || data.old_username !== data.username) {
          applyUsernameUpdate(data.user_id, data.old_username, data.username);
        }

        if (Object.prototype.hasOwnProperty.call(data, 'avatar')) {
          applyAvatarUpdate(data.user_id, data.avatar || '');
        }
      } else if (data.type === 'message.delivery') {
        const receiptSummary = cacheReceiptSummary(data.message_id, data.receipt_summary, data.status || 'sent');
        messages.value = messages.value.map((message) => {
          if (message.id === data.message_id) {
            return {...message, deliveryStatus: receiptSummary.status, receiptSummary};
          }
          return message;
        });
      } else if (data.type === 'device.added') {
        if (Number(data.user_id) === Number(myUserId) && data.active_device_count !== undefined) {
          await updateCurrentDeviceActiveCount(data.active_device_count).catch(console.error);
        }
        if (data.device_id && data.device_id !== currentDeviceId.value) {
          redistributeGroupSenderKeysToNewDevice(data.user_id, data.device_id).catch(console.error);
        }
      } else if (data.type === 'device.revoked') {
        if (Number(data.user_id) === Number(myUserId) && data.active_device_count !== undefined) {
          await updateCurrentDeviceActiveCount(data.active_device_count).catch(console.error);
        }
        if (data.device_id && Number(data.user_id) !== Number(myUserId)) {
          await clearStoredSessionState(getSessionStorageScope(), data.device_id).catch(console.error);
        }
        if (data.device_id && data.device_id === currentDeviceId.value && Number(data.user_id) === Number(myUserId)) {
          ElMessage.error(translateError('设备已被撤销'));
          await handleCurrentDeviceRevoked();
          return;
        }
      } else if (data.type === 'error' && data.detail) {
        ElMessage.error(translateError(data.detail));
      }
    } catch (e) {
      console.error(e);
    }
  };
  await new Promise((resolve, reject) => {
    let settled = false;
    const settle = (fn, value) => {
      if (settled) {
        return;
      }
      settled = true;
      fn(value);
    };

    const openTimer = window.setTimeout(() => {
      settle(reject, new Error('WebSocket connection timed out'));
      socket?.close();
    }, 10000);

    socket.onopen = async () => {
      window.clearTimeout(openTimer);
      clearSocketReconnectTimer();
      socketReconnectAttempts = 0;
      try {
        await flushE2EEOutbox();
      } catch (e) {
        console.error(e);
      } finally {
        settle(resolve);
      }
    };

    socket.onerror = () => {
      window.clearTimeout(openTimer);
      settle(reject, new Error('WebSocket connection failed'));
    };

    socket.onclose = async (event) => {
      window.clearTimeout(openTimer);
      if (!settled) {
        settle(reject, new Error('WebSocket connection closed'));
      }
      if (isRevokedSocketCloseEvent(event)) {
        socket = null;
        ElMessage.error(translateError('设备已被撤销'));
        await handleCurrentDeviceRevoked();
        return;
      }
      requeuePendingOutboxMessages().catch(console.error);
      socket = null;
      scheduleSocketReconnect();
    };
  });

  socket.onerror = (event) => {
    console.error('WebSocket error', event);
  };

  socket.onclose = async (event) => {
    console.warn('WebSocket closed', {code: event.code, reason: event.reason, wasClean: event.wasClean});
    if (isRevokedSocketCloseEvent(event)) {
      socket = null;
      ElMessage.error(translateError('设备已被撤销'));
      await handleCurrentDeviceRevoked();
      return;
    }
    requeuePendingOutboxMessages().catch(console.error);
    socket = null;
    scheduleSocketReconnect();
  };
};

const sendMessage = () => {
  if (!inputText.value.trim() || !currentChatId.value) return;
  if (!currentChatCanSend.value) {
    ElMessage.info(currentChatType.value === 'private' && currentChatUser.value?.canChat === false ? t('privateChatLocked') : t('chatUnavailable'));
    return;
  }
  if (sessionFeatureFlags.e2ee_private_enabled && currentChatType.value === 'private') {
    queueE2EEOutgoingMessage({
      chatId: currentChatId.value,
      chatType: 'private',
      plaintext: inputText.value.trim(),
      msgType: 'text',
    }).catch(console.error);
  } else if (sessionFeatureFlags.e2ee_group_enabled && currentChatType.value === 'group' && currentChatUser.value?.e2eeConversationId) {
    queueE2EEOutgoingMessage({
      chatId: currentChatId.value,
      chatType: 'group',
      plaintext: inputText.value.trim(),
      msgType: 'text',
    }).catch(console.error);
  } else {
    ElMessage.error(t('chatUnavailable'));
  }
};

const isSocketReady = () => {
  return socket && socket.readyState === WebSocket.OPEN;
};

const buildPrivateE2EEPackets = async (plaintext, targetUserId = currentChatId.value) => {
  if (!currentDeviceState.value) {
    throw new Error('当前设备状态不可用');
  }

  const sessionScope = getSessionStorageScope();
  const targetDirectoryRes = await axios.get(`${API_BASE}/e2ee/users/${targetUserId}/prekey-bundle`, {
    headers: {Authorization: `Bearer ${token}`},
    params: {peek: true}
  });
  const targetBundleDevices = targetDirectoryRes.data.devices || [];
  let targetSessions = await ensureSignalSessionsForUserDevices(sessionScope, targetUserId, targetBundleDevices);

  let ownMirrorSessions = [];
  if ((currentDeviceState.value?.activeDeviceCount || 1) > 1) {
    const ownDirectoryRes = await axios.get(`${API_BASE}/e2ee/users/${myUserId}/prekey-bundle`, {
      headers: {Authorization: `Bearer ${token}`},
      params: {peek: true}
    });
    const ownBundleDevices = (ownDirectoryRes.data.devices || []).filter((item) => item.device_id !== currentDeviceId.value);
    ownMirrorSessions = await ensureSignalSessionsForUserDevices(sessionScope, myUserId, ownBundleDevices);
  }

  if (!targetSessions.length) {
    throw new Error('目标用户设备尚未准备好建立 E2EE 会话');
  }

  const packets = [];

  for (const knownSession of targetSessions) {
    let sessionState = knownSession;
    sessionState = attachLocalIdentityToSession(sessionState, currentDeviceState.value);
    const encrypted = await encryptOutgoingMessage({
      scopeKey: sessionScope,
      sessionState,
      plaintext,
    });
    packets.push({
      recipient_user_id: targetUserId,
      recipient_device_id: sessionState.remoteDeviceId,
      envelope_type: 'signal',
      envelope: encrypted.envelope,
    });
  }

  for (const ownSession of ownMirrorSessions) {
    const attachedSession = attachLocalIdentityToSession(ownSession, currentDeviceState.value);
    const encrypted = await encryptOutgoingMessage({
      scopeKey: sessionScope,
      sessionState: attachedSession,
      plaintext,
    });
    packets.push({
      recipient_user_id: myUserId,
      recipient_device_id: ownSession.remoteDeviceId,
      envelope_type: 'signal',
      envelope: encrypted.envelope,
    });
  }

  packets.push({
    recipient_user_id: myUserId,
    recipient_device_id: currentDeviceId.value,
    envelope_type: 'local',
    envelope: await encryptLocalEnvelope(currentDeviceState.value, plaintext),
  });

  return packets;
};

const buildSignalPacketsFromMemberDirectory = async (
  groupDirectory,
  plaintext,
  {includeSelfCurrentDevice = false, targetUserId = null, targetDeviceIds = [], forceNewSessions = false} = {}
) => {
  const sessionScope = getSessionStorageScope();
  const packets = [];
  const targetDeviceSet = new Set((targetDeviceIds || []).map((deviceId) => String(deviceId)));

  for (const member of (groupDirectory.members || [])) {
    if (targetUserId !== null && Number(member.user_id) !== Number(targetUserId)) {
      continue;
    }
    const targetDevices = (member.devices || []).filter((device) => {
      if (member.user_id === myUserId && device.device_id === currentDeviceId.value) {
        return includeSelfCurrentDevice;
      }
      if (targetDeviceSet.size > 0 && !targetDeviceSet.has(String(device.device_id))) {
        return false;
      }
      return true;
    });
    if (!targetDevices.length) continue;

    // Clear existing sessions so ensureSignalSessionsForUserDevices creates
    // brand-new sessions that will encrypt with prekey mode.
    // This ensures the receiver can always rebuild the session from the envelope.
    if (forceNewSessions) {
      for (const device of targetDevices) {
        await clearStoredSessionState(sessionScope, device.device_id);
      }
    }

    const sessions = await ensureSignalSessionsForUserDevices(sessionScope, member.user_id, targetDevices, {
      groupId: groupDirectory.group_id,
    });
    for (const sessionState of sessions) {
      const attachedSession = attachLocalIdentityToSession(sessionState, currentDeviceState.value);
      const encrypted = await encryptOutgoingMessage({
        scopeKey: sessionScope,
        sessionState: attachedSession,
        plaintext,
      });
      packets.push({
        recipient_user_id: member.user_id,
        recipient_device_id: sessionState.remoteDeviceId,
        envelope_type: 'signal',
        envelope: encrypted.envelope,
      });
    }
  }

  return packets;
};

const sendSenderKeyDistributionMessage = (groupId, epoch, packets) => {
  if (!packets.length || !isSocketReady()) {
    return false;
  }
  socket.send(JSON.stringify({
    type: 'message.send',
    to: groupId,
    chat_type: 'group',
    group_epoch: epoch,
    client_message_id: window.crypto.randomUUID(),
    msg_type: 'sender_key_distribution',
    packets,
  }));
  return true;
};

const redistributeGroupSenderKeysToNewDevice = async (targetUserId, targetDeviceId) => {
  if (!sessionFeatureFlags.e2ee_group_enabled || !targetUserId || !targetDeviceId || !isSocketReady()) {
    return;
  }

  const groupContacts = contactList.value.filter((contact) => {
    return contact.type === 'group' && contact.e2eeConversationId;
  });

  for (const groupContact of groupContacts) {
    try {
      const groupDirectory = await fetchGroupMemberDeviceDirectory(groupContact.id, {force: true});
      const targetMember = (groupDirectory.members || []).find((member) => Number(member.user_id) === Number(targetUserId));
      if (!targetMember || !(targetMember.devices || []).some((device) => device.device_id === targetDeviceId)) {
        continue;
      }

      const senderKeyState = await loadGroupSenderKey({
        scopeKey: getSessionStorageScope(),
        groupId: groupDirectory.group_id,
        epoch: groupDirectory.epoch,
        senderDeviceId: currentDeviceId.value,
      });
      if (!senderKeyState) {
        continue;
      }

      const distributionText = buildSenderKeyDistributionPayload({
        groupId: groupDirectory.group_id,
        epoch: groupDirectory.epoch,
        senderDeviceId: currentDeviceId.value,
        senderKeyBase64: senderKeyState.senderKeyBase64,
      });
      const packets = await buildSignalPacketsFromMemberDirectory(groupDirectory, distributionText, {
        targetUserId,
        targetDeviceIds: [targetDeviceId],
        forceNewSessions: true,
      });
      sendSenderKeyDistributionMessage(groupDirectory.group_id, groupDirectory.epoch, packets);
    } catch (error) {
      console.error(error);
    }
  }
};

const requestGroupSenderKeysFromMembers = async (groupId) => {
  if (!sessionFeatureFlags.e2ee_group_enabled || !isSocketReady()) {
    return;
  }
  try {
    await axios.post(`${API_BASE}/e2ee/groups/${groupId}/request-sender-keys`, {}, {
      headers: {Authorization: `Bearer ${token}`}
    });
  } catch (error) {
    console.error(error);
  }
};

const ensureLocalGroupSenderKeyState = async (groupDirectory) => {
  const groupId = groupDirectory.group_id;
  const epoch = groupDirectory.epoch;
  let senderKeyState = await loadGroupSenderKey({
    scopeKey: getSessionStorageScope(),
    groupId,
    epoch,
    senderDeviceId: currentDeviceId.value,
  });
  if (senderKeyState) {
    return senderKeyState;
  }
  senderKeyState = await createGroupSenderKeyState({
    scopeKey: getSessionStorageScope(),
    groupId,
    epoch,
    senderDeviceId: currentDeviceId.value,
  });
  return senderKeyState;
};

const redistributeSenderKeysToGroupMembers = async (groupId) => {
  if (!sessionFeatureFlags.e2ee_group_enabled || !isSocketReady()) {
    return;
  }
  try {
    const groupDirectory = await fetchGroupMemberDeviceDirectory(groupId, {force: true});
    const senderKeyState = await ensureLocalGroupSenderKeyState(groupDirectory);
    const distributionText = buildSenderKeyDistributionPayload({
      groupId,
      epoch: groupDirectory.epoch,
      senderDeviceId: currentDeviceId.value,
      senderKeyBase64: senderKeyState.senderKeyBase64,
    });
    const packets = await buildSignalPacketsFromMemberDirectory(groupDirectory, distributionText, {
      forceNewSessions: true,
    });
    sendSenderKeyDistributionMessage(groupId, groupDirectory.epoch, packets);
  } catch (error) {
    console.error(error);
  }
};

const redistributeSenderKeyToMember = async (groupId, targetUserId) => {
  if (!sessionFeatureFlags.e2ee_group_enabled || !isSocketReady()) {
    return;
  }
  try {
    const groupDirectory = await fetchGroupMemberDeviceDirectory(groupId, {force: true});
    const senderKeyState = await ensureLocalGroupSenderKeyState(groupDirectory);
    const distributionText = buildSenderKeyDistributionPayload({
      groupId,
      epoch: groupDirectory.epoch,
      senderDeviceId: currentDeviceId.value,
      senderKeyBase64: senderKeyState.senderKeyBase64,
    });
    const packets = await buildSignalPacketsFromMemberDirectory(groupDirectory, distributionText, {
      targetUserId: Number(targetUserId),
      forceNewSessions: true,
    });
    if (packets.length > 0) {
      sendSenderKeyDistributionMessage(groupId, groupDirectory.epoch, packets);
    }
  } catch (error) {
    console.error(error);
  }
};

const ensureGroupSenderKeyDistribution = async (groupDirectory) => {
  const groupId = groupDirectory.group_id;
  const epoch = groupDirectory.epoch;
  let senderKeyState = await loadGroupSenderKey({
    scopeKey: getSessionStorageScope(),
    groupId,
    epoch,
    senderDeviceId: currentDeviceId.value,
  });

  if (senderKeyState) {
    return senderKeyState;
  }

  senderKeyState = await ensureLocalGroupSenderKeyState(groupDirectory);

  const distributionText = buildSenderKeyDistributionPayload({
    groupId,
    epoch,
    senderDeviceId: currentDeviceId.value,
    senderKeyBase64: senderKeyState.senderKeyBase64,
  });
  const packets = await buildSignalPacketsFromMemberDirectory(groupDirectory, distributionText, {
    forceNewSessions: true,
  });

  sendSenderKeyDistributionMessage(groupId, epoch, packets);

  return senderKeyState;
};

const buildGroupE2EEPackets = async (plaintext, groupId = currentChatId.value) => {
  if (!currentDeviceState.value) {
    throw new Error('当前设备状态不可用');
  }

  const groupDirectory = await fetchGroupMemberDeviceDirectory(groupId, {force: true});
  const senderKeyState = await ensureGroupSenderKeyDistribution(groupDirectory);
  const groupEnvelope = await encryptGroupSenderKeyMessage({
    groupId,
    epoch: groupDirectory.epoch,
    senderDeviceId: currentDeviceId.value,
    senderKeyBase64: senderKeyState.senderKeyBase64,
    plaintext,
  });

  const packets = [];
  for (const member of (groupDirectory.members || [])) {
    for (const device of (member.devices || [])) {
      packets.push({
        recipient_user_id: member.user_id,
        recipient_device_id: device.device_id,
        envelope_type: 'group_sender_key',
        envelope: groupEnvelope,
      });
    }
  }

  const hasCurrentDevice = packets.some((packet) => packet.recipient_user_id === myUserId && packet.recipient_device_id === currentDeviceId.value);
  if (!hasCurrentDevice) {
    packets.push({
      recipient_user_id: myUserId,
      recipient_device_id: currentDeviceId.value,
      envelope_type: 'group_sender_key',
      envelope: groupEnvelope,
    });
  }

  return {
    packets,
    epoch: groupDirectory.epoch,
  };
};

const dispatchGroupE2EEMessage = async ({chatId, plaintext, msgType = 'text', attachmentBlobIds = [], clientMessageId}) => {
  if (!isSocketReady()) {
    return false;
  }

  const payload = await buildGroupE2EEPackets(plaintext, chatId);
  socket.send(JSON.stringify({
    type: 'message.send',
    to: chatId,
    chat_type: 'group',
    group_epoch: payload.epoch,
    client_message_id: clientMessageId,
    msg_type: msgType,
    attachment_blob_ids: attachmentBlobIds,
    packets: payload.packets,
  }));
  return true;
};

const dispatchPrivateE2EEMessage = async ({chatId, plaintext, msgType = 'text', attachmentBlobIds = [], clientMessageId}) => {
  if (!isSocketReady()) {
    return false;
  }

  const packets = await buildPrivateE2EEPackets(plaintext, chatId);
  socket.send(JSON.stringify({
    type: 'message.send',
    to: chatId,
    chat_type: 'private',
    client_message_id: clientMessageId,
    msg_type: msgType,
    attachment_blob_ids: attachmentBlobIds,
    packets,
  }));
  return true;
};

const requeuePendingOutboxMessages = async () => {
  const scopeKey = getSessionStorageScope();
  const items = await listOutboxMessages(scopeKey);
  for (const item of items) {
    if (item.status === 'pending') {
      await saveOutboxMessage(scopeKey, item.clientMessageId, {...item, status: 'queued'});
      updateMessageStatusByClientId(item.clientMessageId, 'queued');
    }
  }
};

const flushE2EEOutbox = async () => {
  if (outboxFlushInProgress || !isSocketReady() || !currentDeviceState.value) {
    return false;
  }

  outboxFlushInProgress = true;
  try {
    const scopeKey = getSessionStorageScope();
    const outboxItems = (await listOutboxMessages(scopeKey)).filter((item) => item.status !== 'pending');
    for (const item of outboxItems) {
      await saveOutboxMessage(scopeKey, item.clientMessageId, {
        ...item,
        status: 'pending',
        lastAttemptAt: new Date().toISOString(),
      });
      updateMessageStatusByClientId(item.clientMessageId, 'pending');
      try {
        if (item.chatType === 'group') {
          await dispatchGroupE2EEMessage(item);
        } else {
          await dispatchPrivateE2EEMessage(item);
        }
      } catch (e) {
        console.error(e);
        await saveOutboxMessage(scopeKey, item.clientMessageId, {
          ...item,
          status: 'failed',
          lastError: translateError(e.response?.data?.detail) || e.message || 'Failed',
        });
        updateMessageStatusByClientId(item.clientMessageId, 'failed');
      }
    }
    return true;
  } finally {
    outboxFlushInProgress = false;
  }
};

const queueE2EEOutgoingMessage = async ({chatId, chatType, plaintext, msgType = 'text', attachmentBlobIds = []}) => {
  const clientMessageId = window.crypto.randomUUID();
  const queueItem = {
    clientMessageId,
    chatId,
    chatType,
    plaintext,
    msgType,
    attachmentBlobIds,
    createdAt: new Date().toISOString(),
    status: 'queued',
  };
  await saveOutboxMessage(getSessionStorageScope(), clientMessageId, queueItem);
  upsertOutgoingPlaceholderMessage(queueItem);
  if (Number(currentChatId.value) === Number(chatId) && currentChatType.value === chatType) {
    clearDraftForConversation(chatId, chatType);
    inputText.value = '';
  }
  if (isSocketReady()) {
    await flushE2EEOutbox();
  } else {
    ensureRealtimeSocketConnected().catch(console.error);
    ElMessage.info(t('messageQueued'));
  }
  return true;
};

const retryOutgoingMessage = async (msg) => {
  if (!msg?.clientMessageId) {
    return;
  }
  const scopeKey = getSessionStorageScope();
  const item = await loadOutboxMessage(scopeKey, msg.clientMessageId);
  if (!item) {
    return;
  }
  await saveOutboxMessage(scopeKey, msg.clientMessageId, {...item, status: 'queued', lastError: null});
  updateMessageStatusByClientId(msg.clientMessageId, 'queued');
  if (isSocketReady()) {
    await flushE2EEOutbox();
  } else {
    ensureRealtimeSocketConnected().catch(console.error);
  }
};

const canRecallMessage = (msg) => {
  return Boolean(msg?.id)
    && !msg?.isLocalOnly
    && msg?.from === myUserId
    && !isMessageRecalled(msg)
    && msg?.msg_type !== 'sender_key_distribution';
};

const recallMessage = async (msg) => {
  if (!canRecallMessage(msg)) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      t('confirmRecallMessage'),
      t('recallMessage'),
      {
        confirmButtonText: t('recallMessage'),
        cancelButtonText: t('cancel'),
        type: 'warning',
      }
    );
  } catch {
    return;
  }

  try {
    const response = await axios.post(`${API_BASE}/e2ee/messages/${msg.id}/recall`, {}, {
      headers: {Authorization: `Bearer ${token}`}
    });
    await applyMessageRecalledEvent(response.data || {});
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
  }
};

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
  });
};

const applyPresenceStatus = (userId, isOnline) => {
  if (!userId) {
    return;
  }

  const normalizedOnline = Boolean(isOnline);
  const contact = contactList.value.find((item) => item.id === userId && item.type === 'private');
  if (contact) {
    contact.isOnline = normalizedOnline;
  }

  const patchUser = (user) => {
    if (user.id !== userId) {
      return user;
    }
    return {...user, is_online: normalizedOnline};
  };

  searchResults.users = searchResults.users.map(patchUser);
  createGroupSearchResults.value = createGroupSearchResults.value.map(patchUser);
  inviteSearchResults.value = inviteSearchResults.value.map(patchUser);
  allUsers.value = allUsers.value.map(patchUser);
};

const applyPresenceSnapshot = (onlineUserIds = []) => {
  const onlineSet = new Set((onlineUserIds || []).map((value) => Number(value)));

  contactList.value.forEach((contact) => {
    if (contact.type === 'private') {
      contact.isOnline = onlineSet.has(Number(contact.id));
    }
  });

  const patchUser = (user) => ({
    ...user,
    is_online: onlineSet.has(Number(user.id)),
  });

  searchResults.users = searchResults.users.map(patchUser);
  createGroupSearchResults.value = createGroupSearchResults.value.map(patchUser);
  inviteSearchResults.value = inviteSearchResults.value.map(patchUser);
  allUsers.value = allUsers.value.map(patchUser);
};

const getAvatarColor = (id) => {
  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
  return colors[id % colors.length];
};

const sortGroupMembers = (members) => {
  return [...members].sort((left, right) => {
    if (left.role === 'owner' && right.role !== 'owner') return -1;
    if (left.role !== 'owner' && right.role === 'owner') return 1;

    const usernameCompare = (left.username || '').localeCompare(right.username || '', undefined, {
      numeric: true,
      sensitivity: 'base'
    });
    if (usernameCompare !== 0) return usernameCompare;

    return left.id - right.id;
  });
};

const getMessageSenderAvatar = (msg) => {
  if (currentChatType.value === 'group') {
    return (msg.username || 'U').charAt(0).toUpperCase();
  }
  if (msg.from === myUserId) return myUsername.value.charAt(0).toUpperCase();
  return currentChatUser.value?.username.charAt(0).toUpperCase();
};

// 文件上传与附件展示。
const fileInput = ref(null);
const triggerUpload = () => {
  if (!currentChatCanSend.value) {
    ElMessage.info(currentChatType.value === 'private' && currentChatUser.value?.canChat === false ? t('privateChatLocked') : t('chatUnavailable'));
    return;
  }
  fileInput.value.click();
};
const handleFileUpload = async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  if (!currentChatCanSend.value) {
    ElMessage.info(currentChatType.value === 'private' && currentChatUser.value?.canChat === false ? t('privateChatLocked') : t('chatUnavailable'));
    event.target.value = '';
    return;
  }
  if (!isSocketReady()) {
    ElMessage.error(t('connectionNotReady'));
    event.target.value = '';
    return;
  }
  const allowed = ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'zip', 'txt'];
  const ext = file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    ElMessage.error("Unsupported file");
    event.target.value = '';
    return;
  }
  const formData = new FormData();
  formData.append('file', file);
  try {
    ElMessage.info("Uploading...");
    if ((currentChatType.value === 'private' && sessionFeatureFlags.e2ee_private_enabled) || (currentChatType.value === 'group' && sessionFeatureFlags.e2ee_group_enabled && currentChatUser.value?.e2eeConversationId)) {
      const encryptedFile = await encryptAttachmentFile(file);
      const initRes = await axios.post(`${API_BASE}/e2ee/attachments/init`, {
        mime_type: encryptedFile.mimeType,
        ciphertext_size: encryptedFile.ciphertextSize,
        ciphertext_sha256: encryptedFile.ciphertextSha256,
      }, {
        headers: {Authorization: `Bearer ${token}`}
      });

      await axios.put(
        `${API_BASE}/e2ee/attachments/${initRes.data.blob_id}`,
        encryptedFile.ciphertextBytes,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/octet-stream'
          }
        }
      );

      await axios.post(`${API_BASE}/e2ee/attachments/${initRes.data.blob_id}/complete`, {
        ciphertext_sha256: encryptedFile.ciphertextSha256,
      }, {
        headers: {Authorization: `Bearer ${token}`}
      });

      const descriptor = buildEncryptedAttachmentDescriptor({
        blobId: initRes.data.blob_id,
        file,
        fileKeyBase64: encryptedFile.fileKeyBase64,
        nonceBase64: encryptedFile.nonceBase64,
      });

      if (currentChatType.value === 'group' && currentChatUser.value?.e2eeConversationId) {
        await queueE2EEOutgoingMessage({
          chatId: currentChatId.value,
          chatType: 'group',
          plaintext: JSON.stringify(descriptor),
          msgType: descriptor.mime_type.startsWith('image/') ? 'image' : 'file',
          attachmentBlobIds: [descriptor.blob_id],
        });
      } else {
        await queueE2EEOutgoingMessage({
          chatId: currentChatId.value,
          chatType: 'private',
          plaintext: JSON.stringify(descriptor),
          msgType: descriptor.mime_type.startsWith('image/') ? 'image' : 'file',
          attachmentBlobIds: [descriptor.blob_id],
        });
      }
      await loadEncryptedAttachmentUrl(descriptor);
    } else {
      ElMessage.error(t('chatUnavailable'));
    }
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || "Upload failed");
  } finally {
    event.target.value = '';
  }
};

const getMsgType = (msg) => {
  if (isMessageRecalled(msg)) return 'text';
  if (msg.msg_type && msg.msg_type !== 'text') return msg.msg_type;
  const descriptor = parseEncryptedAttachmentDescriptor(msg.content);
  if (descriptor) {
    return descriptor.mime_type?.startsWith('image/') ? 'image' : 'file';
  }
  return 'text';
};

const loadEncryptedAttachmentUrl = async (descriptor) => {
  if (!descriptor?.blob_id) return '';
  if (attachmentObjectUrls[descriptor.blob_id]) return attachmentObjectUrls[descriptor.blob_id];
  if (attachmentLoadPromises.has(descriptor.blob_id)) {
    return await attachmentLoadPromises.get(descriptor.blob_id);
  }

  const task = axios.get(`${API_BASE}/e2ee/attachments/${descriptor.blob_id}`, {
    headers: {Authorization: `Bearer ${token}`},
    responseType: 'arraybuffer'
  }).then(async (response) => {
    const plaintextBytes = await decryptAttachmentCiphertext({
      ciphertextBytes: new Uint8Array(response.data),
      fileKeyBase64: descriptor.file_key,
      nonceBase64: descriptor.file_nonce,
    });
    const blobUrl = URL.createObjectURL(new Blob([plaintextBytes], {
      type: descriptor.mime_type || 'application/octet-stream'
    }));
    attachmentObjectUrls[descriptor.blob_id] = blobUrl;
    return blobUrl;
  }).finally(() => {
    attachmentLoadPromises.delete(descriptor.blob_id);
  });

  attachmentLoadPromises.set(descriptor.blob_id, task);
  return await task;
};

const resolveAttachmentUrl = async (content) => {
  const descriptor = parseEncryptedAttachmentDescriptor(content);
  if (descriptor) {
    return await loadEncryptedAttachmentUrl(descriptor);
  }
  return getFileUrl(content);
};

const getFileUrl = (content) => {
  const descriptor = parseEncryptedAttachmentDescriptor(content);
  if (descriptor) {
    if (attachmentObjectUrls[descriptor.blob_id]) return attachmentObjectUrls[descriptor.blob_id];
    const errorCount = attachmentLoadErrors[descriptor.blob_id] || 0;
    if (errorCount < 3 && !attachmentLoadPromises.has(descriptor.blob_id)) {
      loadEncryptedAttachmentUrl(descriptor).catch((err) => {
        console.error('[E2EE] attachment load failed:', descriptor.blob_id, err);
        attachmentLoadErrors[descriptor.blob_id] = errorCount + 1;
      });
    }
    return '';
  }
  return '';
};

const isAttachmentLoadFailed = (content) => {
  const descriptor = parseEncryptedAttachmentDescriptor(content);
  if (!descriptor) return true;
  return (attachmentLoadErrors[descriptor.blob_id] || 0) >= 3;
};

const getFileName = (content) => {
  const descriptor = parseEncryptedAttachmentDescriptor(content);
  if (descriptor) {
    return descriptor.file_name || 'File';
  }
  return 'File';
};

const openUserSearchResult = async (user) => {
  if (!user.can_start_chat && !user.has_conversation) {
    ElMessage.info(t('addFriendToChat'));
    return;
  }

  const conversation = ensureConversationEntry({
    id: user.id,
    username: user.username,
    avatar: user.avatar || '',
    type: 'private',
    isOnline: user.is_online,
    isTemporary: !user.has_conversation,
    canChat: user.can_start_chat
  });
  await selectChat(conversation);
};

const openGroupSearchResult = async (group) => {
  if (!group.is_member) {
    if (group.invite_status === 'pending') {
      ElMessage.info(t('acceptInviteHint'));
      return;
    }
    if (group.join_request_status === 'pending') {
      ElMessage.info(t('joinRequestPendingHint'));
      return;
    }
    ElMessage.info(t('requestToJoin'));
    return;
  }

  const existingConversation = contactList.value.find(contact => {
    return contact.id === group.id && contact.type === 'group';
  });
  const conversation = existingConversation || {
    id: group.id,
    username: group.name,
    avatar: group.avatar || '',
    type: 'group',
    isOnline: true
  };
  const opened = await selectChat(conversation);

  if (opened && !existingConversation) {
    ensureConversationEntry(conversation);
  }
};

const sendFriendRequest = async (user) => {
  const actionKey = buildFriendActionKey(user.id);
  friendActionTarget.value = actionKey;
  try {
    const res = await axios.post(
      `${API_BASE}/user/friends/requests`,
      {user_id: user.id},
      {headers: {Authorization: `Bearer ${token}`}}
    );
    updateUserRelationshipInCollections(user.id, 'outgoing_pending', res.data.request_id, false);
    await loadFriendData();
    ElMessage.success(t('friendRequestSent'));
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

const acceptFriendRequest = async (requestId, userId) => {
  const actionKey = buildFriendActionKey(userId);
  friendActionTarget.value = actionKey;
  try {
    await axios.post(`${API_BASE}/user/friends/requests/${requestId}/accept`, {}, {
      headers: {Authorization: `Bearer ${token}`}
    });
    updateUserRelationshipInCollections(userId, 'friend', null, true);
    await loadFriendData();
    ElMessage.success(t('friendRequestAccepted'));
  } catch (e) {
    const detail = e.response?.data?.detail;
    if (detail === '好友关系已存在' || detail === '该好友请求已处理') {
      await Promise.all([loadContacts(), loadFriendData(), refreshSearchResultsIfNeeded()]);
      if (friendsList.value.some(friend => friend.id === userId)) {
        updateUserRelationshipInCollections(userId, 'friend', null, true);
        ElMessage.success(t('friendRequestAccepted'));
        return;
      }
    }
    ElMessage.error(translateError(detail) || t('searchFailed'));
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

const rejectFriendRequest = async (requestId, userId) => {
  const actionKey = buildFriendActionKey(userId);
  friendActionTarget.value = actionKey;
  try {
    await axios.post(`${API_BASE}/user/friends/requests/${requestId}/reject`, {}, {
      headers: {Authorization: `Bearer ${token}`}
    });
    updateUserRelationshipInCollections(userId, 'none', null, false);
    await loadFriendData();
    ElMessage.success(t('friendRequestRejected'));
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

const cancelFriendRequest = async (requestId, userId) => {
  const actionKey = buildFriendActionKey(userId);
  friendActionTarget.value = actionKey;
  try {
    await axios.delete(`${API_BASE}/user/friends/requests/${requestId}`, {
      headers: {Authorization: `Bearer ${token}`}
    });
    updateUserRelationshipInCollections(userId, 'none', null, false);
    await loadFriendData();
    ElMessage.success(t('friendRequestCancelled'));
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

const removeFriend = async (friendId) => {
  const actionKey = buildFriendActionKey(friendId);
  friendActionTarget.value = actionKey;
  try {
    await axios.delete(`${API_BASE}/user/friends/${friendId}`, {
      headers: {Authorization: `Bearer ${token}`}
    });
    updateUserRelationshipInCollections(friendId, 'none', null, false);
    await loadFriendData();
    ElMessage.success(t('friendRemoved'));
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

const createGroupJoinRequest = async (groupId) => {
  const actionKey = buildGroupActionKey(groupId);
  friendActionTarget.value = actionKey;
  try {
    const res = await axios.post(`${API_BASE}/chat/group/${groupId}/join-requests`, {}, {
      headers: {Authorization: `Bearer ${token}`}
    });
    updateGroupAccessStateInSearch(groupId, {
      join_request_status: 'pending',
      join_request_id: res.data.request_id,
      invite_status: null,
      invite_id: null
    });
    await loadGroupAccessData();
    ElMessage.success(t('joinRequestSent'));
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

const cancelGroupJoinRequest = async (requestId, groupId) => {
  const actionKey = buildGroupActionKey(groupId);
  friendActionTarget.value = actionKey;
  try {
    await axios.delete(`${API_BASE}/chat/group/join-requests/${requestId}`, {
      headers: {Authorization: `Bearer ${token}`}
    });
    updateGroupAccessStateInSearch(groupId, {
      join_request_status: null,
      join_request_id: null
    });
    await loadGroupAccessData();
    ElMessage.success(t('joinRequestCancelled'));
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

const acceptGroupInvite = async (inviteId, groupId) => {
  const actionKey = buildGroupActionKey(groupId);
  friendActionTarget.value = actionKey;
  try {
    await axios.post(`${API_BASE}/chat/group/invites/${inviteId}/accept`, {}, {
      headers: {Authorization: `Bearer ${token}`}
    });
    updateGroupAccessStateInSearch(groupId, {
      invite_status: null,
      invite_id: null,
      join_request_status: null,
      join_request_id: null,
      is_member: true
    });
    await Promise.all([loadContacts(), loadGroupAccessData(), refreshSearchResultsIfNeeded()]);
    ElMessage.success(t('groupInviteAccepted'));
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

const rejectGroupInvite = async (inviteId, groupId) => {
  const actionKey = buildGroupActionKey(groupId);
  friendActionTarget.value = actionKey;
  try {
    await axios.post(`${API_BASE}/chat/group/invites/${inviteId}/reject`, {}, {
      headers: {Authorization: `Bearer ${token}`}
    });
    updateGroupAccessStateInSearch(groupId, {
      invite_status: null,
      invite_id: null
    });
    await loadGroupAccessData();
    ElMessage.success(t('groupInviteRejected'));
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

const createGroupInvite = async (groupId, userId, options = {}) => {
  const {silent = false} = options;
  const actionKey = buildGroupActionKey(userId);
  friendActionTarget.value = actionKey;
  try {
    await axios.post(`${API_BASE}/chat/group/${groupId}/invites`, {user_id: userId}, {
      headers: {Authorization: `Bearer ${token}`}
    });
    inviteSelection.value = inviteSelection.value.filter(id => id !== userId);
    inviteSearchResults.value = inviteSearchResults.value.map(user => {
      if (user.id === userId) {
        return {...user, invite_status: 'pending'};
      }
      return user;
    });
    await loadGroupAccessData();
    if (currentChatId.value === groupId) {
      await loadCurrentGroupInvites(groupId);
    }
    if (!silent) {
      ElMessage.success(t('groupInviteCreated'));
    }
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
    throw e;
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

const approveGroupJoinRequest = async (requestId, groupId) => {
  const actionKey = buildGroupActionKey(requestId);
  friendActionTarget.value = actionKey;
  try {
    await axios.post(`${API_BASE}/chat/group/join-requests/${requestId}/approve`, {}, {
      headers: {Authorization: `Bearer ${token}`}
    });
    const refreshTasks = [loadContacts(), loadGroupAccessData(), refreshSearchResultsIfNeeded()];
    await Promise.all(refreshTasks);
    if (groupManageVisible.value && currentChatType.value === 'group' && currentChatId.value === groupId) {
      await fetchGroupMembers();
    }
    ElMessage.success(t('groupJoinApproved'));
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

const cancelGroupInvite = async (inviteId, groupId) => {
  const actionKey = buildGroupActionKey(groupId);
  friendActionTarget.value = actionKey;
  try {
    await axios.delete(`${API_BASE}/chat/group/invites/${inviteId}`, {
      headers: {Authorization: `Bearer ${token}`}
    });
    currentGroupInvites.value = currentGroupInvites.value.filter(invite => invite.id !== inviteId);
    updateGroupAccessStateInSearch(groupId, {
      invite_status: null,
      invite_id: null
    });
    await loadGroupAccessData();
    ElMessage.success(t('groupInviteCancelled'));
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

const rejectGroupJoinRequest = async (requestId, groupId) => {
  const actionKey = buildGroupActionKey(requestId);
  friendActionTarget.value = actionKey;
  try {
    await axios.post(`${API_BASE}/chat/group/join-requests/${requestId}/reject`, {}, {
      headers: {Authorization: `Bearer ${token}`}
    });
    await loadGroupAccessData();
    ElMessage.success(t('groupJoinRejected'));
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || t('searchFailed'));
  } finally {
    if (friendActionTarget.value === actionKey) {
      friendActionTarget.value = '';
    }
  }
};

// 账户设置。
const settingsVisible = ref(false);
const logoutConfirmVisible = ref(false);
const logoutPending = ref(false);
const activeTab = ref('profile');
const loading = ref(false);
const settingsForm = reactive({
  newUsername: myUsername.value,
  oldPassword: '',
  newPassword: ''
});

const applyUsernameUpdate = (userId, oldUsername, newUsername) => {
  if (userId === myUserId) {
    myUsername.value = newUsername;
    localStorage.setItem('username', newUsername);
    settingsForm.newUsername = newUsername;
  }

  contactList.value = contactList.value.map(contact => {
    if (contact.type === 'private' && contact.id === userId) {
      return {...contact, username: newUsername};
    }

    if (
      contact.type === 'group' &&
      oldUsername &&
      contact.lastMessage?.startsWith(`${oldUsername}: `)
    ) {
      return {
        ...contact,
        lastMessage: `${newUsername}: ${contact.lastMessage.slice(oldUsername.length + 2)}`
      };
    }

    return contact;
  });

  messages.value = messages.value.map(message => {
    if (message.from === userId) {
      return {...message, username: newUsername};
    }
    return message;
  });

  groupMembers.value = sortGroupMembers(groupMembers.value.map(member => {
    if (member.id === userId) {
      return {...member, username: newUsername};
    }
    return member;
  }));

  allUsers.value = allUsers.value.map(user => {
    if (user.id === userId) {
      return {...user, username: newUsername};
    }
    return user;
  });

  searchResults.users = searchResults.users.map(user => {
    if (user.id === userId) {
      return {...user, username: newUsername};
    }
    return user;
  });

  const privateDraftKey = getConversationKey(userId, 'private');
  if (privateDraftKey in conversationDrafts.value) {
    conversationDrafts.value = {
      ...conversationDrafts.value,
      [privateDraftKey]: {
        ...normalizeDraftEntry(conversationDrafts.value[privateDraftKey]),
        username: newUsername,
        type: 'private'
      }
    };
    persistConversationDrafts();
  }

  if (oldUsername) {
    const previewScope = getPreviewStorageScope();
    const groupPreviewMap = getGroupPreviewMap(myUserId, previewScope);
    let didUpdateGroupPreviewMap = false;
    Object.entries(groupPreviewMap).forEach(([groupId, entry]) => {
      if (entry?.text?.startsWith(`${oldUsername}: `)) {
        groupPreviewMap[groupId] = {
          ...entry,
          text: `${newUsername}: ${entry.text.slice(oldUsername.length + 2)}`,
        };
        didUpdateGroupPreviewMap = true;
      }
    });
    if (didUpdateGroupPreviewMap) {
      replaceGroupPreviewMap(myUserId, groupPreviewMap, previewScope);
    }
  }

  createGroupSearchResults.value = createGroupSearchResults.value.map(user => {
    if (user.id === userId) {
      return {...user, username: newUsername};
    }
    return user;
  });

  inviteSearchResults.value = inviteSearchResults.value.map(user => {
    if (user.id === userId) {
      return {...user, username: newUsername};
    }
    return user;
  });

  incomingFriendRequests.value = incomingFriendRequests.value.map(request => {
    if (request.user.id === userId) {
      return {...request, user: {...request.user, username: newUsername}};
    }
    return request;
  });

  outgoingFriendRequests.value = outgoingFriendRequests.value.map(request => {
    if (request.user.id === userId) {
      return {...request, user: {...request.user, username: newUsername}};
    }
    return request;
  });

  friendsList.value = friendsList.value.map(friend => {
    if (friend.id === userId) {
      return {...friend, username: newUsername};
    }
    return friend;
  });

  receivedGroupInvites.value = receivedGroupInvites.value.map(invite => {
    if (invite.inviter.id === userId) {
      return {...invite, inviter: {...invite.inviter, username: newUsername}};
    }
    if (invite.invitee.id === userId) {
      return {...invite, invitee: {...invite.invitee, username: newUsername}};
    }
    return invite;
  });

  currentGroupInvites.value = currentGroupInvites.value.map(invite => {
    if (invite.inviter.id === userId) {
      return {...invite, inviter: {...invite.inviter, username: newUsername}};
    }
    if (invite.invitee.id === userId) {
      return {...invite, invitee: {...invite.invitee, username: newUsername}};
    }
    return invite;
  });

  myGroupJoinRequests.value = myGroupJoinRequests.value.map(request => {
    if (request.requester.id === userId) {
      return {...request, requester: {...request.requester, username: newUsername}};
    }
    return request;
  });

  ownedGroupJoinRequests.value = ownedGroupJoinRequests.value.map(request => {
    if (request.requester.id === userId) {
      return {...request, requester: {...request.requester, username: newUsername}};
    }
    return request;
  });
};

const applyAvatarUpdate = (userId, newAvatar) => {
  const avatar = newAvatar || '';

  if (userId === myUserId) {
    myAvatar.value = avatar;
    if (avatar) {
      localStorage.setItem('avatar', avatar);
    } else {
      localStorage.removeItem('avatar');
    }
  }

  contactList.value = contactList.value.map(contact => {
    if (contact.type === 'private' && contact.id === userId) {
      return {...contact, avatar};
    }
    return contact;
  });

  messages.value = messages.value.map(message => {
    if (message.from === userId) {
      return {...message, avatar};
    }
    return message;
  });

  groupMembers.value = sortGroupMembers(groupMembers.value.map(member => {
    if (member.id === userId) {
      return {...member, avatar};
    }
    return member;
  }));

  allUsers.value = allUsers.value.map(user => {
    if (user.id === userId) {
      return {...user, avatar};
    }
    return user;
  });

  searchResults.users = searchResults.users.map(user => {
    if (user.id === userId) {
      return {...user, avatar};
    }
    return user;
  });

  createGroupSearchResults.value = createGroupSearchResults.value.map(user => {
    if (user.id === userId) {
      return {...user, avatar};
    }
    return user;
  });

  inviteSearchResults.value = inviteSearchResults.value.map(user => {
    if (user.id === userId) {
      return {...user, avatar};
    }
    return user;
  });

  incomingFriendRequests.value = incomingFriendRequests.value.map(request => {
    if (request.user.id === userId) {
      return {...request, user: {...request.user, avatar}};
    }
    return request;
  });

  outgoingFriendRequests.value = outgoingFriendRequests.value.map(request => {
    if (request.user.id === userId) {
      return {...request, user: {...request.user, avatar}};
    }
    return request;
  });

  friendsList.value = friendsList.value.map(friend => {
    if (friend.id === userId) {
      return {...friend, avatar};
    }
    return friend;
  });

  receivedGroupInvites.value = receivedGroupInvites.value.map(invite => {
    if (invite.inviter.id === userId) {
      return {...invite, inviter: {...invite.inviter, avatar}};
    }
    if (invite.invitee.id === userId) {
      return {...invite, invitee: {...invite.invitee, avatar}};
    }
    return invite;
  });

  currentGroupInvites.value = currentGroupInvites.value.map(invite => {
    if (invite.inviter.id === userId) {
      return {...invite, inviter: {...invite.inviter, avatar}};
    }
    if (invite.invitee.id === userId) {
      return {...invite, invitee: {...invite.invitee, avatar}};
    }
    return invite;
  });

  myGroupJoinRequests.value = myGroupJoinRequests.value.map(request => {
    if (request.requester.id === userId) {
      return {...request, requester: {...request.requester, avatar}};
    }
    return request;
  });

  ownedGroupJoinRequests.value = ownedGroupJoinRequests.value.map(request => {
    if (request.requester.id === userId) {
      return {...request, requester: {...request.requester, avatar}};
    }
    return request;
  });
};

const handleProfileCommand = (command) => {
  if (command === 'logout') logoutConfirmVisible.value = true;
  else if (command === 'settings') {
    settingsVisible.value = true;
    settingsForm.newUsername = myUsername.value;
    settingsForm.oldPassword = '';
    settingsForm.newPassword = '';
    clearPendingAvatarSelection('profile');
  }
};
const handleLogout = async () => {
  if (logoutPending.value) {
    return;
  }
  logoutPending.value = true;
  try {
    if (currentDeviceId.value) {
      await clearOutboxMessages(getSessionStorageScope()).catch(console.error);
    }
    await logoutSession();
  } catch (error) {
    console.error(error);
  } finally {
    token = '';
    logoutConfirmVisible.value = false;
    settingsVisible.value = false;
    if (socket) socket.close();
    logoutPending.value = false;
    window.location.replace(router.resolve('/').href);
  }
};
const saveProfile = async () => {
  const newName = settingsForm.newUsername.trim();
  const isNameChanged = newName && newName !== myUsername.value;
  const isAvatarChanged = !!pendingAvatarBlob.value;

  if (!isNameChanged && !isAvatarChanged) {
    ElMessage.info(currentLang.value === 'en' ? 'No changes made' : '未作任何修改');
    settingsVisible.value = false;
    return;
  }
  
  try {
    await ElMessageBox.confirm(
      currentLang.value === 'en' ? 'Are you sure you want to save these changes?' : '确认保存修改吗？', 
      currentLang.value === 'en' ? 'Confirm Action' : '操作确认', 
      {
        confirmButtonText: t('accept'),
        cancelButtonText: t('cancel'),
        type: 'info',
      }
    );
  } catch {
    return;
  }

  loading.value = true;
  try {
    if (isNameChanged) {
      const res = await axios.put(
        `${API_BASE}/user/username`,
        {new_username: newName},
        {headers: {Authorization: `Bearer ${token}`}}
      );
      if (myUsername.value !== res.data.username) {
        applyUsernameUpdate(myUserId, myUsername.value, res.data.username);
      }
    }

    if (isAvatarChanged) {
      const formData = new FormData();
      formData.append('file', pendingAvatarBlob.value, getAvatarUploadFilename(pendingAvatarBlob.value, 'avatar'));
      const res = await axios.post(`${API_BASE}/user/avatar`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      applyAvatarUpdate(myUserId, res.data.avatar);
      clearPendingAvatarSelection('profile');
    }

    settingsVisible.value = false;
    ElMessage.success({ message: currentLang.value === 'en' ? 'Profile updated successfully' : '个人资料更新成功', type: 'success' });
  } catch (e) {
    ElMessage.error({ message: translateError(e.response?.data?.detail) || "Failed", type: 'error' });
  } finally {
    loading.value = false;
  }
};
const updatePassword = async () => {
  if (!settingsForm.oldPassword || !settingsForm.newPassword) return;
  
  try {
    await ElMessageBox.confirm(
      currentLang.value === 'en' ? 'Are you sure you want to change your password? You will need to login again.' : '确认修改密码吗？修改后将重新登录。', 
      currentLang.value === 'en' ? 'Confirm Action' : '操作确认', 
      {
        confirmButtonText: t('accept'),
        cancelButtonText: t('cancel'),
        type: 'info',
      }
    );
  } catch {
    return;
  }

  loading.value = true;
  try {
    await axios.put(
      `${API_BASE}/user/password`,
      {
        old_password: settingsForm.oldPassword,
        new_password: settingsForm.newPassword
      },
      {headers: {Authorization: `Bearer ${token}`}}
    );
    ElMessage.success({ message: t('passwordUpdated'), type: 'success' });
    handleLogout();
  } catch (e) {
    ElMessage.error({ message: translateError(e.response?.data?.detail) || "Failed", type: 'error' });
  } finally {
    loading.value = false;
  }
};

// 创建群组。
const openCreateGroup = async () => {
  if (createGroupSearchTimer) clearTimeout(createGroupSearchTimer);
  createGroupSearchAbortController?.abort();
  createGroupSearchAbortController = null;
  createGroupSearchRequestId += 1;
  clearPendingAvatarSelection('create-group');
  createGroupVisible.value = true;
  newGroupName.value = '';
  selectedMembers.value = [];
  createGroupMemberSearch.value = '';
  createGroupSearchResults.value = [];
  createGroupSearchLoading.value = true;
  createGroupSearchError.value = '';
  createGroupSearchHasMore.value = false;
  createGroupSearchNextOffset.value = 0;
  createGroupSearchPaginationTouched.value = false;
  createGroupSearchLoadingMore.value = false;
  await resetScrollPosition('create');
  try {
    await loadAllUsers();
  } finally {
    createGroupSearchLoading.value = false;
    await updateScrollUi('create');
  }
};
const toggleSelection = (userId) => {
  const index = selectedMembers.value.indexOf(userId);
  if (index > -1) selectedMembers.value.splice(index, 1);
  else selectedMembers.value.push(userId);
};

const uploadGroupAvatarFile = async (groupId) => {
  if (!pendingGroupAvatarBlob.value) return;

  const formData = new FormData();
  formData.append('file', pendingGroupAvatarBlob.value, getAvatarUploadFilename(pendingGroupAvatarBlob.value, 'group-avatar'));
  const res = await axios.post(`${API_BASE}/chat/group/${groupId}/avatar`, formData, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'multipart/form-data'
    }
  });

  currentGroupAvatar.value = res.data.avatar;
  clearPendingAvatarSelection('group');
};

const submitCreateGroup = async () => {
  if (!newGroupName.value.trim()) {
    ElMessage.warning(t('groupNamePlaceholder'));
    return;
  }
  if (selectedMembers.value.length === 0) {
    ElMessage.warning(t('selectMembersRequired'));
    return;
  }
  try {
    const res = await axios.post(
      `${API_BASE}/chat/group/create`,
      {
        name: newGroupName.value.trim(),
        members: selectedMembers.value
      },
      {headers: {Authorization: `Bearer ${token}`}}
    );

    if (pendingGroupAvatarBlob.value) {
      try {
        await uploadGroupAvatarFile(res.data.group_id);
      } catch (avatarError) {
        console.error(avatarError);
        clearPendingAvatarSelection('create-group');
        createGroupVisible.value = false;
        ElMessage.warning(t('groupCreatedAvatarFailed'));
        return;
      }
    }

    clearPendingAvatarSelection('create-group');
    createGroupVisible.value = false;
    ElMessage.success(t('groupCreated'));
  } catch (e) {
    ElMessage.error("Failed");
  }
};

// 群组管理。
const fetchGroupMembers = async (options = {}) => {
  const {syncMeta = false} = options;
  try {
    const res = await axios.get(`${API_BASE}/chat/group/${currentChatId.value}/members`, {
      headers: {Authorization: `Bearer ${token}`}
    });
    groupMembers.value = sortGroupMembers(res.data.members || []);
    if (syncMeta) {
      editingGroupName.value = res.data.name || currentChatUser.value?.username || '';
    }
    if (syncMeta || !pendingGroupAvatarBlob.value) {
      currentGroupAvatar.value = res.data.avatar || '';
    }
    isGroupOwner.value = res.data.owner_id === myUserId;
  } catch (e) {
    if (e.response && [403, 404].includes(e.response.status) && currentChatId.value !== null) {
      removeInvalidGroupConversation(currentChatId.value);
      ElMessage.info(t('groupUnavailable'));
      return;
    }
    console.error(e);
  }
};

const openGroupManage = async () => {
  clearPendingAvatarSelection('group');
  groupManageVisible.value = true;
  editingGroupName.value = currentChatUser.value?.username || '';
  currentGroupAvatar.value = currentChatUser.value?.avatar || '';
  await fetchGroupMembers({syncMeta: true});
};

const updateGroup = async () => {
  const newName = editingGroupName.value.trim();
  const currentName = currentChatUser.value?.username || '';
  const isNameChanged = Boolean(newName) && newName !== currentName;
  const isAvatarChanged = Boolean(pendingGroupAvatarBlob.value);

  if (!newName) return;
  if (!isNameChanged && !isAvatarChanged) {
    ElMessage.info(currentLang.value === 'en' ? 'No changes made' : '未作任何修改');
    return;
  }

  try {
    if (isNameChanged) {
      const res = await axios.put(
        `${API_BASE}/chat/group/${currentChatId.value}`,
        {name: newName},
        {headers: {Authorization: `Bearer ${token}`}}
      );
      editingGroupName.value = res.data.name;
    }

    if (isAvatarChanged) {
      await uploadGroupAvatarFile(currentChatId.value);
    }

    const refreshTasks = [loadContacts(), refreshSearchResultsIfNeeded()];
    if (notificationCenterVisible.value) {
      refreshTasks.push(loadGroupAccessData());
    }
    await Promise.all(refreshTasks);
    ElMessage.success(t('groupUpdated'));
    groupManageVisible.value = false;
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || "Update failed");
  }
};

const disbandGroup = async () => {
  if (!confirm(t('confirmDisband'))) return;
  try {
    await axios.delete(`${API_BASE}/chat/group/${currentChatId.value}`, {
      headers: {Authorization: `Bearer ${token}`}
    });
    ElMessage.success(t('disbandSuccess'));
    clearDraftForConversation(currentChatId.value, currentChatType.value);
    await loadContacts();
    currentGroupAvatar.value = '';
    clearPendingAvatarSelection('group');
    currentChatId.value = null;
    inputText.value = '';
    groupManageVisible.value = false;
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || "Failed");
  }
};

// 成员邀请与移除。
const openInviteDialog = async () => {
  if (inviteSearchTimer) clearTimeout(inviteSearchTimer);
  inviteSearchAbortController?.abort();
  inviteSearchAbortController = null;
  inviteSearchRequestId += 1;
  inviteVisible.value = true;
  inviteSelection.value = [];
  inviteSearch.value = '';
  inviteSearchResults.value = [];
  inviteSearchLoading.value = true;
  inviteSearchError.value = '';
  inviteSearchHasMore.value = false;
  inviteSearchNextOffset.value = 0;
  inviteSearchPaginationTouched.value = false;
  inviteSearchLoadingMore.value = false;
  await resetScrollPosition('invite');
  currentGroupInvites.value = [];
  try {
    await Promise.all([loadAllUsers(), loadCurrentGroupInvites(currentChatId.value)]);
  } finally {
    inviteSearchLoading.value = false;
    await updateScrollUi('invite');
  }
};
const toggleInviteSelection = (userId) => {
  const index = inviteSelection.value.indexOf(userId);
  if (index > -1) inviteSelection.value.splice(index, 1);
  else inviteSelection.value.push(userId);
};
const submitInvite = async () => {
  if (inviteSelection.value.length === 0) return;
  try {
    for (const userId of inviteSelection.value) {
      await createGroupInvite(currentChatId.value, userId, {silent: true});
    }
    ElMessage.success(t('groupInviteCreated'));
    inviteVisible.value = false;
    await loadGroupAccessData();
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || "Invite failed");
  }
};
const kickMember = async (userId) => {
  if (!confirm(t('confirmRemoveMember'))) return;
  try {
    await axios.delete(`${API_BASE}/chat/group/${currentChatId.value}/member/${userId}`, {
      headers: {Authorization: `Bearer ${token}`}
    });
    ElMessage.success(t('removeMemberSuccess'));
    await fetchGroupMembers();
  } catch (e) {
    ElMessage.error(translateError(e.response?.data?.detail) || "Remove failed");
  }
};
</script>

<style scoped>
/* 布局 */
.telegram-layout {
  display: flex;
  height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  overflow: hidden;
}

/* 侧边栏 */
.sidebar {
  width: 320px;
  background-color: #ffffff;
  border-right: 1px solid #dfe1e5;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 12px 10px;
  display: flex;
  align-items: center;
  gap: 10px;
}

:deep(.search-input .el-input__inner) {
  text-overflow: ellipsis;
}

.lang-switch,
.action-btn {
  width: 32px;
  height: 32px;
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #707579;
  transition: transform 0.2s;
}

.action-btn-badge {
  position: relative;
}

.header-badge {
  position: absolute;
  top: 2px;
  right: 0;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: #ef4444;
  color: white;
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  text-align: center;
}

.lang-switch:hover,
.action-btn:hover {
  transform: scale(1.1);
  color: #3390ec;
}

.lang-icon {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.search-input {
  flex: 1;
}

.contact-list {
  flex: 1;
  overflow-y: auto;
  position: relative;
  box-sizing: border-box;
}

.contact-list.with-scroll-actions {
  padding-bottom: 76px;
}

.result-section {
  padding-top: 6px;
}

.result-section-title {
  padding: 0 14px 6px;
  font-size: 12px;
  font-weight: 700;
  color: #707579;
  text-transform: uppercase;
}

.search-skeleton-list {
  padding: 6px 10px 12px;
}

.compact-skeleton-list {
  padding-top: 2px;
}

.picker-skeleton-list {
  padding: 6px 10px 10px;
}

.search-skeleton-item,
.picker-skeleton-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  margin: 5px 0;
  border-radius: 10px;
}

.picker-skeleton-item {
  padding: 10px 2px;
  margin: 0;
}

.skeleton-avatar,
.skeleton-line,
.skeleton-time {
  background: linear-gradient(90deg, #eef2f7 25%, #f7f9fc 50%, #eef2f7 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.2s ease-in-out infinite;
}

.skeleton-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  flex-shrink: 0;
}

.skeleton-avatar.small {
  width: 32px;
  height: 32px;
}

.skeleton-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skeleton-line {
  height: 10px;
  border-radius: 999px;
}

.skeleton-line.long {
  width: 78%;
}

.skeleton-line.medium {
  width: 58%;
}

.skeleton-line.short {
  width: 38%;
}

.skeleton-time {
  width: 42px;
  height: 10px;
  border-radius: 999px;
  flex-shrink: 0;
}

@keyframes skeleton-shimmer {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0 50%;
  }
}

.sidebar-empty-hint {
  padding: 24px 18px;
}

.subtle-end-hint {
  padding: 4px 14px 12px;
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
}

.list-floating-actions {
  position: absolute;
  right: 12px;
  bottom: 12px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  z-index: 3;
  pointer-events: none;
}

.picker-list-actions {
  bottom: 10px;
}

.scroll-end-pill,
.scroll-top-btn {
  pointer-events: auto;
  border-radius: 999px;
  font-size: 12px;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12);
}

.scroll-end-pill {
  padding: 6px 10px;
  color: #64748b;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(203, 213, 225, 0.8);
}

.scroll-top-btn {
  border: 1px solid rgba(51, 144, 236, 0.18);
  background: rgba(51, 144, 236, 0.96);
  color: white;
  padding: 8px 12px;
  cursor: pointer;
}

.scroll-top-btn:hover {
  background: rgba(37, 99, 235, 0.96);
}

.list-floating-actions {
  position: absolute;
  right: 12px;
  bottom: 12px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  z-index: 3;
  pointer-events: none;
}

.picker-list-actions {
  bottom: 10px;
}

.scroll-end-pill,
.scroll-top-btn {
  pointer-events: auto;
  border-radius: 999px;
  font-size: 12px;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12);
}

.scroll-end-pill {
  padding: 6px 10px;
  color: #64748b;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(203, 213, 225, 0.8);
}

.scroll-top-btn {
  border: 1px solid rgba(51, 144, 236, 0.18);
  background: rgba(51, 144, 236, 0.96);
  color: white;
  padding: 8px 12px;
  cursor: pointer;
}

.scroll-top-btn:hover {
  background: rgba(37, 99, 235, 0.96);
}

.contact-item {
  display: flex;
  padding: 10px;
  cursor: pointer;
  border-radius: 10px;
  margin: 5px;
  transition: background 0.2s;
}

.contact-item:hover {
  background-color: #f4f4f5;
}

.contact-item.active {
  background-color: #3390ec;
  color: white;
}

.contact-item.active .username,
.contact-item.active .time,
.contact-item.active .last-message {
  color: white;
}

.logout-text {
  color: #ff595a;
}

.hidden-file-input {
  display: none;
}

.avatar {
  position: relative;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  color: white;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 18px;
  font-weight: bold;
  margin-right: 10px;
  flex-shrink: 0;
}

.online-dot {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 12px;
  height: 12px;
  background-color: #10b981;
  border: 2px solid white;
  border-radius: 50%;
}

.contact-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
}

.info-top,
.info-bottom {
  display: flex;
  justify-content: space-between;
}

.name-with-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.item-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.search-user-actions,
.friend-request-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 10px;
  flex-shrink: 0;
}

.username {
  font-weight: 600;
  font-size: 15px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.time {
  font-size: 12px;
  color: #aaaaaa;
}

.last-message {
  font-size: 14px;
  color: #707579;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
}

.unread-badge {
  background-color: #c4c9cc;
  color: white;
  padding: 0 6px;
  border-radius: 10px;
  font-size: 12px;
  min-width: 18px;
  text-align: center;
}

.contact-item.active .unread-badge {
  background-color: white;
  color: #3390ec;
}

.search-result-item .info-top {
  align-items: center;
}

.search-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
}

.search-tag.joined {
  color: #0f766e;
  background-color: rgba(16, 185, 129, 0.12);
}

.friend-tag {
  align-self: center;
}

.search-tag.locked {
  color: #b45309;
  background-color: rgba(245, 158, 11, 0.14);
}

.search-tag.draft {
  color: #475569;
  background-color: rgba(148, 163, 184, 0.18);
}

.temp-close-btn {
  border: none;
  background: rgba(148, 163, 184, 0.18);
  color: #64748b;
  width: 20px;
  height: 20px;
  border-radius: 999px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  line-height: 1;
  padding: 0;
}

.temp-close-btn:hover {
  background: rgba(148, 163, 184, 0.28);
}

.friend-action-btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: white;
  color: #334155;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 10px;
  cursor: pointer;
}

.friend-action-btn.primary {
  background: #3390ec;
  border-color: #3390ec;
  color: white;
}

.friend-action-btn.ghost {
  background: #f8fafc;
}

.friend-action-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.contact-item.active .temp-close-btn {
  background: rgba(255, 255, 255, 0.22);
  color: white;
}

.my-profile {
  padding: 0;
  border-top: 1px solid #dfe1e5;
  background-color: #f7f7f7;
  height: 60px;
  display: flex;
  align-items: center;
}

.my-profile :deep(.el-dropdown) {
  width: 100%;
  height: 100%;
}

.profile-card {
  display: flex;
  align-items: center;
  padding: 0 16px;
  width: 100%;
  height: 100%;
  cursor: pointer;
  box-sizing: border-box;
}

.profile-card:hover {
  background-color: #ededed;
}

.mini-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  color: white;
  display: flex;
  justify-content: center;
  align-items: center;
  font-weight: bold;
  font-size: 14px;
  margin-right: 12px;
  flex-shrink: 0;
}

.profile-info {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.profile-name {
  font-weight: 600;
  font-size: 14px;
  color: #000;
}

.profile-id {
  font-size: 11px;
  color: #707579;
}

.profile-settings-icon {
  color: #707579;
  display: flex;
  align-items: center;
  transition: transform 0.3s;
}

.profile-card:hover .profile-settings-icon {
  transform: rotate(90deg);
  color: #3390ec;
}

/* 聊天主区 */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: #93b3c8;
  background-image: url('../assets/chat-bg.svg');
  background-size: cover;
  background-position: center;
  position: relative;
}

.chat-header {
  height: 56px;
  background-color: white;
  padding: 0 20px;
  display: flex;
  align-items: center;
   justify-content: space-between;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  z-index: 10;
}

.header-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.header-name {
  font-weight: 600;
  font-size: 16px;
  margin-right: 10px;
}

.header-status {
  font-size: 13px;
  color: #999;
}

.header-status.online-text {
  color: #3390ec;
}

.header-status.group-hint {
  color: #707579;
  font-size: 12px;
  cursor: pointer;
}

.header-status.group-hint:hover {
  text-decoration: underline;
  color: #3390ec;
}

.cursor-pointer {
  cursor: pointer;
}

.messages-area {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-row {
  display: flex;
  align-items: flex-end;
  max-width: 70%;
  gap: 8px;
  margin-bottom: 12px;
}

.my-message {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: white;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 14px;
  margin: 0 8px;
  flex-shrink: 0;
}

.message-bubble {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.985) 0%, rgba(250, 252, 255, 0.97) 100%);
  padding: 10px 12px 8px;
  border-radius: 20px 20px 20px 8px;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.09);
  border: 1px solid rgba(214, 224, 235, 0.88);
  position: relative;
  width: fit-content;
  display: inline-flex;
  flex-direction: column;
  gap: 7px;
  max-width: min(440px, calc(100vw - 160px));
  word-break: break-word;
  overflow-wrap: break-word;
  white-space: pre-wrap;
}

.my-message .message-bubble {
  background: linear-gradient(180deg, rgba(239, 253, 222, 0.99) 0%, rgba(231, 248, 214, 0.97) 100%);
  border-radius: 20px 20px 8px 20px;
  border-color: rgba(198, 228, 173, 0.95);
  box-shadow: 0 8px 18px rgba(111, 163, 82, 0.14);
}

.group-peer-bubble {
  padding-top: 10px;
}

.bubble-header {
  display: flex;
  align-items: center;
   gap: 8px;
  min-width: 0;
  margin-bottom: -1px;
}

.bubble-footer {
  align-self: flex-end;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
  color: #8b98a5;
  letter-spacing: 0.01em;
}

.bubble-status-text {
  color: #5f6f7f;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recalled-message-content {
  color: #7c8794;
  font-style: italic;
}

.bubble-retry-btn {
  border: none;
  background: transparent;
  color: #d97706;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
}

.bubble-recall-btn {
  border: none;
  background: transparent;
  color: #dc2626;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
}

.bubble-read-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  border-radius: 4px;
  padding: 1px 3px;
  margin: -1px -3px;
}

.bubble-read-status:hover .bubble-status-text {
  color: #3b82f6;
}

.read-avatars {
  display: inline-flex;
  align-items: center;
  flex-direction: row-reverse;
}

.read-avatar {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1.5px solid #fff;
  color: #fff;
  font-size: 8px;
  font-weight: 700;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  flex-shrink: 0;
  position: relative;
}

.read-avatar .avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.read-receipt-popover {
  position: fixed;
  z-index: 9999;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(15, 23, 42, 0.18);
  padding: 8px 0;
  min-width: 200px;
  max-width: 280px;
  color: #1f2937;
}

.read-receipt-overlay {
  position: fixed;
  inset: 0;
  z-index: 9998;
}

.popover-header {
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
  padding: 2px 14px 8px;
  border-bottom: 1px solid #f3f4f6;
  margin-bottom: 4px;
}

.popover-list {
  max-height: 260px;
  overflow-y: auto;
}

.popover-reader {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 14px;
  cursor: default;
}

.popover-reader:hover {
  background: #f9fafb;
}

.popover-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  flex-shrink: 0;
}

.popover-avatar .avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.popover-info {
  min-width: 0;
}

.popover-name {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.popover-time {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 1px;
}

.msg-sender-name {
  display: inline-flex;
  align-items: center;
  max-width: 240px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.01em;
  line-height: 1.15;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.message-content {
  font-size: 15px;
  line-height: 1.45;
  color: #18222d;
}

/* 底部输入区 */
.input-area {
  background-color: white;
  padding: 10px 16px;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  border-top: 1px solid #dfe1e5;
  min-height: 56px;
}

.attach-btn,
.send-icon-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s;
  flex-shrink: 0;
}

.attach-btn {
  color: #707579;
}

.attach-btn:hover {
  background-color: #f4f4f5;
  color: #3390ec;
}

.attach-btn.disabled-action,
.send-icon-btn.disabled-action {
  opacity: 0.45;
  cursor: not-allowed;
  pointer-events: none;
}

.attach-btn.disabled-action:hover,
.send-icon-btn.disabled-action:hover {
  background-color: transparent;
  color: inherit;
}

.send-icon-btn {
  color: #999;
  pointer-events: none;
}

.send-icon-btn.active {
  color: #3390ec;
  pointer-events: auto;
}

.send-icon-btn.active:hover {
  background-color: #eff6fd;
}

.chat-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 10px 0;
  font-size: 16px;
  outline: none;
  resize: none;
  max-height: 120px;
  font-family: inherit;
  line-height: 1.5;
}

.chat-input:disabled {
  color: #94a3b8;
  cursor: not-allowed;
}

.icon {
  fill: currentColor;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  background-color: #f0f2f5;
  color: #666;
}

.empty-content {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 10px 20px;
  border-radius: 20px;
}

/* 附件消息 */
.message-image {
  margin: 0;
  position: relative;
}

.message-image img {
  max-width: 100%;
  max-height: 320px;
  border-radius: 16px;
  display: block;
  cursor: pointer;
}

.image-loading-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 120px;
  min-height: 80px;
  border-radius: 16px;
  background: rgba(120, 120, 140, 0.08);
  color: rgba(100, 100, 120, 0.7);
  font-size: 13px;
}

.image-loading-placeholder .load-failed-text {
  opacity: 0.65;
}

.image-loading-placeholder .loading-spinner-text {
  animation: pulse-opacity 1.5s ease-in-out infinite;
}

@keyframes pulse-opacity {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.media-bubble {
  padding: 8px;
  gap: 8px;
}

.media-bubble .bubble-footer {
  position: absolute;
  right: 14px;
  bottom: 14px;
  margin: 0;
  padding: 4px 7px;
  border-radius: 999px;
  background: rgba(20, 31, 45, 0.42);
  color: rgba(255, 255, 255, 0.96);
  box-shadow: 0 6px 14px rgba(15, 23, 42, 0.16);
  backdrop-filter: blur(6px);
}

.message-file {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 180px;
  padding-right: 6px;
}

.file-icon {
  font-size: 24px;
}

.file-name {
  color: #3390ec;
  text-decoration: none;
  font-weight: 500;
}

/* 弹窗 */
:deep(.tg-dialog) {
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
}

:deep(.tg-dialog .el-dialog__header) {
  margin: 0;
  padding: 20px 24px;
  border-bottom: 1px solid #f0f0f0;
}

:deep(.tg-dialog .el-dialog__title) {
  font-weight: 600;
  font-size: 18px;
}

:deep(.tg-dialog .el-dialog__body) {
  padding: 0;
}

.tg-dialog-content {
  padding: 24px;
}

.confirm-dialog-text {
  font-size: 14px;
  line-height: 1.6;
  color: #475569;
}

.input-group {
  margin-bottom: 20px;
}

.compact-input-group {
  margin-bottom: 14px;
}

.input-group label {
  display: block;
  margin-bottom: 8px;
  color: #707579;
  font-size: 14px;
  font-weight: 500;
}

.tg-input :deep(.el-input__wrapper) {
  border-radius: 10px;
  padding: 8px 12px;
  box-shadow: 0 0 0 1px #dfe1e5 inset;
}

.tg-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px #3390ec inset !important;
}

.tg-btn {
  border: none;
  padding: 10px 20px;
  border-radius: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}

.tg-btn.primary {
  background-color: #3390ec;
  color: white;
  width: 100%;
}

.tg-btn.primary:hover {
  background-color: #2884d8;
}

.tg-btn.danger {
  background-color: #ff595a;
  color: white;
  width: 100%;
}

.tg-btn.danger:hover {
  background-color: #e54d4e;
}

.tg-btn.ghost {
  background: transparent;
  color: #3390ec;
}

.tg-btn.ghost:hover {
  background-color: #f0f8ff;
}

.dialog-footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 10px;
}

.friend-request-list {
  min-height: 220px;
}

.friend-request-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #f1f5f9;
}

.friend-request-info {
  flex: 1;
  min-width: 0;
}

.friend-request-name {
  font-weight: 600;
  color: #0f172a;
}

.request-subtitle {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.secondary-action {
  color: #64748b;
}

.danger-text {
  color: #dc2626;
}

.group-manage-actions {
  justify-content: space-between;
  margin-top: 20px;
}

.dialog-footer-actions .tg-btn {
  width: auto;
}

.section-title {
  font-size: 14px;
  color: #3390ec;
  font-weight: 600;
  margin-bottom: 12px;
}

.section-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.add-member-btn {
  font-size: 13px;
  color: #3390ec;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}

.add-member-btn:hover {
  text-decoration: underline;
}

.user-select-list {
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  position: relative;
  box-sizing: border-box;
}

.user-select-list.with-scroll-actions {
  padding-bottom: 68px;
}

.user-select-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  cursor: pointer;
  transition: background 0.1s;
  border-bottom: 1px solid #f9f9f9;
}

.user-select-item:hover {
  background-color: #f4f4f5;
}

.select-name {
  flex: 1;
  font-weight: 500;
  margin-left: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.pointer-events-none {
  pointer-events: none;
}

.role-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: normal;
}

.role-badge.owner {
  background-color: #3390ec20;
  color: #3390ec;
}

.kick-btn {
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.2s;
  display: flex;
}

.kick-btn:hover {
  opacity: 1;
}

.empty-hint {
  text-align: center;
  color: #999;
  padding: 20px;
  font-size: 14px;
}

.avatar-section {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.large-avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  color: white;
  font-size: 32px;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
}

.cropper-view-box,
.cropper-face {
  border-radius: 50%;
}
</style>
