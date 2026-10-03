"use client";

import React, { useState } from "react";
import Image from "next/image";
import { FlaskConical, Settings, BookOpen, ChevronDown, ChevronUp, ChevronRight, Cpu } from "lucide-react";
import NotebookTree from "@/features/notebook/components/NotebookTree";
import styles from "./Sidebar.module.css";

export default function Sidebar() {
  const [isNotebookOpen, setIsNotebookOpen] = useState(true);
  return (
    <div className={styles.sidebarContainer}>
      <div className={styles.logoSection}>
        <Image src="/logo.png" alt="Artifical Soul Logo" width={120} height={120} className={styles.logoImage} />
        <div className={styles.logoText}>
          <span className={styles.logoTitle}>Artificial Soul</span>
          <span className={styles.logoSubtitle}>More than just an AI</span>
        </div>
      </div>

      <nav className={styles.navSection}>
        <button className={styles.navItem}>
          <div className={styles.navItemLeft}>
            <FlaskConical size={28} />
            <span>정보</span>
          </div>
          <ChevronRight size={28} className={styles.arrowIcon} />
        </button>

        <button className={styles.navItem}>
          <div className={styles.navItemLeft}>
            <Settings size={28} />
            <span>설정</span>
          </div>
          <ChevronRight size={28} className={styles.arrowIcon} />
        </button>

        <button
          className={`${styles.navItem} ${isNotebookOpen ? styles.navItemActive : ""}`}
          onClick={() => setIsNotebookOpen((prev) => !prev)}
          type="button"
        >
          <div className={styles.navItemLeft}>
            <BookOpen size={28} />
            <span>노트북</span>
          </div>
          {isNotebookOpen ? <ChevronUp size={24} className={styles.arrowIcon} /> : <ChevronDown size={24} className={styles.arrowIcon} />}
        </button>
      </nav>

      <div className={`${styles.accordionWrapper} ${!isNotebookOpen ? styles.accordionClosed : ""}`}>
        <div className={styles.accordionInner}>
          <div className={styles.notebookDrawer}>
            <NotebookTree />
          </div>
        </div>
      </div>

      <div className={styles.bottomSection}>
        <div className={styles.bottomCard}>
          <div className={styles.cardLeft}>
            <div className={styles.cardIcon}>
              <Cpu size={16} />
            </div>
            <span className={styles.cardTitle}>About Us</span>
          </div>
          <ChevronRight size={14} className={styles.arrowIcon} />
        </div>
      </div>
    </div>
  );
}
