import axios from "axios";
import { FolderItem, ChatItem } from "../types";

export const createFolderApi = async (title: string): Promise<FolderItem> => {
  //백엔드 나오면 주소에서 받아오게 변경
  await new Promise((resolve) => setTimeout(resolve, 300));

  return {
    id: `folder-${Date.now()}`,
    title: title || "새 폴더",
    chatCount: 0,
    isOpen: true,
    chats: [],
  };
};

export const createChatApi = async (folderId: string): Promise<{ folderId: string; chat: ChatItem }> => {
  await new Promise((resolve) => setTimeout(resolve, 300));

  return {
    folderId,
    chat: {
      id: `char-${Date.now()}`,
      title: "새로운 대화",
    },
  };
};

export const moveChatToFolderApi = async (chatId: string, targetFolderId: string): Promise<boolean> => {
  await new Promise((resolve) => setTimeout(resolve, 300));
  //백엔드 연동시 예시
  // await axio.patch(`/api/chats/${chatId}`, {folderId: targetFolderId});
  return true;
};
