"use client";

import React, { useState, useEffect } from "react";
import {
  FolderPlus,
  MessageSquarePlus,
  Search,
  Folder,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  MoreVertical,
  Pencil,
  Trash2,
} from "lucide-react";
import { MOCK_FOLDERS } from "@/features/notebook/mockData";
import { FolderItem, ChatItem } from "@/features/notebook/types";
import styles from "./NotebookTree.module.css";
import { Check, X } from "lucide-react";
import { createFolderApi, createChatApi } from "../apis/folderApi";

export default function NotebookTree() {
  const [folders, setFolders] = useState<FolderItem[]>(MOCK_FOLDERS);
  const [activeChatId, setActiveChatId] = useState<string>("chat-1");
  const [activeFolderId, setActiveFolderId] = useState<string | null>("default-folder");
  const [isCreatingFolder, setIsCreatingFolder] = useState<boolean>(false);
  const [newFolderName, setNewFolderName] = useState<string>("");
  const [draggedChat, setDraggedChat] = useState<{ folderId: string; chatId: string } | null>(null);
  const [dragOverFolderId, setDragOverFolderId] = useState<string | null>(null);
  const [menuTarget, setMenuTarget] = useState<{
    type: "folder" | "chat";
    id: string;
    openUp?: boolean;
  } | null>(null);
  const [editingTarget, setEditingTarget] = useState<{ type: "folder" | "chat"; id: string } | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>("");

  useEffect(() => {
    const handleCloseMenu = () => setMenuTarget(null);
    window.addEventListener("click", handleCloseMenu);
    return () => window.removeEventListener("click", handleCloseMenu);
  }, []);

  const toggleFolder = (folderId: string) => {
    setActiveFolderId(folderId);
    setFolders((prev) => prev.map((folder) => (folder.id === folderId ? { ...folder, isOpen: !folder.isOpen } : folder)));
  };

  const handleConfirmCreateFolder = async () => {
    const trimmed = newFolderName.trim();
    if (!trimmed) {
      setIsCreatingFolder(false);
      return;
    }
    const createdFolder = await createFolderApi(trimmed);

    setFolders((prev) => {
      if (prev.length === 0) return [createdFolder];
      const [defaultFolder, ...rest] = prev;
      return [defaultFolder, createdFolder, ...rest];
    });
    setActiveFolderId(createdFolder.id);
    setNewFolderName("");
    setIsCreatingFolder(false);
  };

  const handleCreateChat = async () => {
    const targetFolderId = activeFolderId || folders[0]?.id;
    if (!targetFolderId) return;

    const { folderId, chat } = await createChatApi(targetFolderId);

    setFolders((prev) =>
      prev.map((f) => {
        if (f.id === folderId) {
          const updated = [chat, ...(f.chats || [])];
          return { ...f, isOpen: true, chatCount: updated.length, chats: updated };
        }
        return f;
      }),
    );
    setActiveChatId(chat.id);
  };

  const handleDropChatToFolder = (targetFolderId: string) => {
    if (!draggedChat) return;
    const { folderId: sourceFolderId, chatId } = draggedChat;

    if (sourceFolderId === targetFolderId) {
      setDraggedChat(null);
      setDragOverFolderId(null);
      return;
    }

    setFolders((prev) => {
      let targetChat: ChatItem | undefined = undefined;
      const sourceFolder = prev.find((f) => f.id === sourceFolderId);
      if (sourceFolder && sourceFolder.chats) {
        targetChat = sourceFolder.chats.find((c) => c.id === chatId);
      }
      if (!targetChat) return prev;

      return prev.map((f) => {
        if (f.id === sourceFolderId) {
          const remaining = (f.chats || []).filter((c) => c.id !== chatId);
          return { ...f, chats: remaining, chatCount: remaining.length };
        }
        if (f.id === targetFolderId) {
          const appended = [targetChat, ...(f.chats || [])];
          return {
            ...f,
            isOpen: true,
            chats: appended,
            chatCount: appended.length,
          };
        }
        return f;
      });
    });

    setDraggedChat(null);
    setDragOverFolderId(null);
  };

  const handleSaveRename = () => {
    if (!editingTarget || !editingTitle.trim()) {
      setEditingTarget(null);
      return;
    }

    if (editingTarget.type === "chat") {
      setFolders((prev) =>
        prev.map((f) => ({
          ...f,
          chats: f.chats?.map((c) => (c.id === editingTarget.id ? { ...c, title: editingTitle.trim() } : c)),
        })),
      );
    } else {
      setFolders((prev) => prev.map((f) => (f.id === editingTarget.id ? { ...f, title: editingTitle.trim() } : f)));
    }
    setEditingTarget(null);
  };

  const handleDeleteItem = (type: "folder" | "chat", id: string) => {
    if (type === "chat") {
      setFolders((prev) =>
        prev.map((f) => {
          const filtered = (f.chats || []).filter((c) => c.id !== id);
          return { ...f, chats: filtered, chatCount: filtered.length };
        }),
      );
    } else {
      setFolders((prev) => prev.filter((f) => f.id !== id));
      if (activeFolderId === id) setActiveFolderId(null);
    }
    setMenuTarget(null);
  };

  return (
    <div className={styles.container}>
      <div className={styles.actionSection}>
        <button className={styles.actionBtn} type="button" onClick={() => setIsCreatingFolder(true)}>
          <div className={styles.actionBtnLeft}>
            <FolderPlus size={16} />
            <span>새 폴더 생성</span>
          </div>
          <span className={styles.plusIcon}>+</span>
        </button>

        <button className={styles.actionBtn} type="button" onClick={handleCreateChat}>
          <div className={styles.actionBtnLeft}>
            <MessageSquarePlus size={16} />
            <span>새 채팅</span>
          </div>
          <span className={styles.plusIcon}>+</span>
        </button>
      </div>

      <div className={styles.searchSection}>
        <div className={styles.searchBox}>
          <Search size={14} className={styles.searchIcon} />
          <input type="text" placeholder="검색..." className={styles.searchInput} />
        </div>
      </div>

      <div className={styles.treeSection} onClick={() => setActiveFolderId(null)}>
        {folders.map((folder, index) => (
          <React.Fragment key={folder.id}>
            <div>
              {/* 폴더 헤더 */}
              <div
                className={`${styles.folderHeader} ${activeFolderId === folder.id ? styles.folderHeaderActive : ""}`}
                onClick={(e) => {
                  e.stopPropagation();
                  toggleFolder(folder.id);
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  if (draggedChat && draggedChat.folderId !== folder.id) {
                    setDragOverFolderId(folder.id);
                  }
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  if (draggedChat && draggedChat.folderId !== folder.id) {
                    setDragOverFolderId(folder.id);
                  }
                }}
                onDragLeaveCapture={() => {
                  if (dragOverFolderId === folder.id) setDragOverFolderId(null);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  handleDropChatToFolder(folder.id);
                }}
              >
                <div className={styles.folderLeft}>
                  <Folder size={15} color="#94a3b8" />
                  {editingTarget?.type === "folder" && editingTarget.id === folder.id ? (
                    <input
                      type="text"
                      className={styles.inlineEditInput}
                      value={editingTitle}
                      onChange={(e) => setEditingTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleSaveRename();
                        if (e.key === "Escape") setEditingTarget(null);
                      }}
                      onBlur={handleSaveRename}
                      autoFocus
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : (
                    <span className={folder.isOpen ? styles.folderTitleActive : styles.folderTitle}>{folder.title}</span>
                  )}
                </div>
                <div className={styles.folderRight}>
                  <span>{folder.chatCount} chats</span>
                  <button
                    type="button"
                    className={`${styles.moreActionBtn} ${
                      menuTarget?.type === "folder" && menuTarget.id === folder.id ? styles.moreActionBtnActive : ""
                    }`}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (menuTarget?.id === folder.id) {
                        setMenuTarget(null);
                      } else {
                        const btnRect = e.currentTarget.getBoundingClientRect();

                        const containerRect = e.currentTarget.closest(`.${styles.treeSection}`)?.getBoundingClientRect();
                        const containerBottom = containerRect ? containerRect.bottom : window.innerHeight;
                        const spaceBelow = containerBottom - btnRect.bottom;

                        setMenuTarget({ type: "folder", id: folder.id, openUp: spaceBelow < 80 });
                      }
                    }}
                  >
                    <MoreVertical size={13} />
                  </button>
                  {folder.isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </div>

                {menuTarget?.type === "folder" && menuTarget.id === folder.id && (
                  <div
                    className={`${styles.actionDropdown} ${menuTarget.openUp ? styles.actionDropdownUp : ""}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      type="button"
                      className={styles.actionMenuItem}
                      onClick={() => {
                        setEditingTarget({ type: "folder", id: folder.id });
                        setEditingTitle(folder.title);
                        setMenuTarget(null);
                      }}
                    >
                      <Pencil size={12} />
                      <span>이름 변경</span>
                    </button>
                    <button
                      type="button"
                      className={`${styles.actionMenuItem} ${styles.actionMenuDelete}`}
                      onClick={() => handleDeleteItem("folder", folder.id)}
                    >
                      <Trash2 size={12} />
                      <span>삭제</span>
                    </button>
                  </div>
                )}
              </div>

              {/* 하위 채팅방 목록 */}
              {folder.isOpen && folder.chats && folder.chats.length > 0 && (
                <div className={styles.chatList}>
                  {folder.chats.map((chat) => {
                    const isActive = activeChatId === chat.id;
                    const isEditing = editingTarget?.type === "chat" && editingTarget.id === chat.id;
                    return (
                      <div
                        key={chat.id}
                        draggable={!isEditing}
                        onDragStart={() => {
                          setDraggedChat({ folderId: folder.id, chatId: chat.id });
                        }}
                        onDragEnd={() => {
                          setDraggedChat(null);
                          setDragOverFolderId(null);
                        }}
                        onDragOver={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          if (draggedChat && draggedChat.folderId !== folder.id) {
                            setDragOverFolderId(folder.id);
                          }
                        }}
                        onDrop={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleDropChatToFolder(folder.id);
                        }}
                        className={`${styles.chatItem} ${isActive ? styles.chatItemActive : ""}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveChatId(chat.id);
                          setActiveFolderId(folder.id);
                        }}
                      >
                        <div className={styles.chatItemLeft}>
                          <MessageSquare size={13} />
                          {isEditing ? (
                            <input
                              type="text"
                              className={styles.inlineEditInput}
                              value={editingTitle}
                              onChange={(e) => setEditingTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") handleSaveRename();
                                if (e.key === "Escape") setEditingTarget(null);
                              }}
                              onBlur={handleSaveRename}
                              autoFocus
                              onClick={(e) => e.stopPropagation()}
                            />
                          ) : (
                            <span>{chat.title}</span>
                          )}
                        </div>

                        {!isEditing && (
                          <button
                            type="button"
                            className={`${styles.moreActionBtn} ${
                              menuTarget?.type === "chat" && menuTarget.id === chat.id ? styles.moreActionBtnActive : ""
                            }`}
                            onClick={(e) => {
                              e.stopPropagation();
                              if (menuTarget?.id === chat.id) {
                                setMenuTarget(null);
                              } else {
                                const btnRect = e.currentTarget.getBoundingClientRect();
                                // 🌟 스크롤 박스(.treeSection)의 바닥 위치와 비교
                                const containerRect = e.currentTarget.closest(`.${styles.treeSection}`)?.getBoundingClientRect();
                                const containerBottom = containerRect ? containerRect.bottom : window.innerHeight;
                                const spaceBelow = containerBottom - btnRect.bottom;

                                setMenuTarget({ type: "chat", id: chat.id, openUp: spaceBelow < 80 });
                              }
                            }}
                          >
                            <MoreVertical size={13} />
                          </button>
                        )}

                        {menuTarget?.type === "chat" && menuTarget.id === chat.id && (
                          <div
                            className={`${styles.actionDropdown} ${menuTarget.openUp ? styles.actionDropdownUp : ""}`}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              type="button"
                              className={styles.actionMenuItem}
                              onClick={() => {
                                setEditingTarget({ type: "chat", id: chat.id });
                                setEditingTitle(chat.title);
                                setMenuTarget(null);
                              }}
                            >
                              <Pencil size={12} />
                              <span>이름 변경</span>
                            </button>
                            <button
                              type="button"
                              className={`${styles.actionMenuItem} ${styles.actionMenuDelete}`}
                              onClick={() => handleDeleteItem("chat", chat.id)}
                            >
                              <Trash2 size={12} />
                              <span>삭제</span>
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {index === 0 && isCreatingFolder && (
              <div className={styles.newFolderInputBox}>
                <input
                  type="text"
                  placeholder="폴더 이름 입력..."
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleConfirmCreateFolder();
                    if (e.key === "Escape") setIsCreatingFolder(false);
                  }}
                  autoFocus
                  className={styles.newFolderInput}
                />
                <div className={styles.newFolderBtnGroup}>
                  <button className={styles.iconBtn} onClick={handleConfirmCreateFolder} type="button" title="확인">
                    <Check size={14} color="#38bdf8" />
                  </button>
                  <button className={styles.iconBtn} onClick={() => setIsCreatingFolder(false)} type="button" title="취소">
                    <X size={14} />
                  </button>
                </div>
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
