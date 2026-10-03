"use client";

import React, { useState } from "react";
import { FolderPlus, MessageSquarePlus, Search, Folder, MessageSquare, ChevronDown, ChevronUp } from "lucide-react";
import { MOCK_FOLDERS } from "@/features/notebook/mockData";
import { FolderItem } from "@/features/notebook/types";
import styles from "./NotebookTree.module.css";
import { Check, X } from "lucide-react";
import { createFolderApi, createChatApi } from "../apis/folderApi";

export default function NotebookTree() {
  const [folders, setFolders] = useState<FolderItem[]>(MOCK_FOLDERS);
  // 디자인 확인용 기본 선택된 채팅 ID
  const [activeChatId, setActiveChatId] = useState<string>("chat-1");

  //현재 선택된 활성 폴더
  const [activeFolderId, setActiveFolderId] = useState<string | null>("default-folder");
  //새 폴더 입력창 열림 여부 및 입력 텍스트
  const [isCreatingFolder, setIsCreatingFolder] = useState<boolean>(false);
  const [newFolderName, setNewFolderName] = useState<string>("");

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
              >
                <div className={styles.folderLeft}>
                  <Folder size={15} color="#94a3b8" />
                  <span className={folder.isOpen ? styles.folderTitleActive : styles.folderTitle}>{folder.title}</span>
                </div>
                <div className={styles.folderRight}>
                  <span>{folder.chatCount} chats</span>
                  {folder.isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </div>
              </div>

              {/* 하위 채팅방 목록 */}
              {folder.isOpen && folder.chats && folder.chats.length > 0 && (
                <div className={styles.chatList}>
                  {folder.chats.map((chat) => {
                    const isActive = activeChatId === chat.id;
                    return (
                      <div
                        key={chat.id}
                        className={`${styles.chatItem} ${isActive ? styles.chatItemActive : ""}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveChatId(chat.id);
                          setActiveFolderId(folder.id);
                        }}
                      >
                        <MessageSquare size={13} />
                        <span>{chat.title}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* 기본 폴더 아래에 인라인 입력창 렌더링 */}
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
