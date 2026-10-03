// src/features/notebook/mockData.ts
import { FolderItem } from "./types";

export const MOCK_FOLDERS: FolderItem[] = [
  {
    id: "default-folder", // 기본 폴더 전용 고유 ID
    title: "기본 폴더",
    chatCount: 0,
    isOpen: true,
    chats: [],
  },
];
