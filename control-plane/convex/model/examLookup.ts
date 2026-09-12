import type { Doc } from "../_generated/dataModel";
import type { DatabaseReader } from "../_generated/server";

export async function examByExamId(db: DatabaseReader, examId: string): Promise<Doc<"exams"> | null> {
  return db
    .query("exams")
    .withIndex("by_exam_id", (q) => q.eq("exam_id", examId))
    .unique();
}

export async function existingExam(db: DatabaseReader, examId: string): Promise<Doc<"exams">> {
  const exam = await examByExamId(db, examId);
  if (exam === null) {
    throw new Error(`exam ${examId} does not exist`);
  }
  return exam;
}

export async function examMessages(db: DatabaseReader, examId: string): Promise<Doc<"exam_messages">[]> {
  return db
    .query("exam_messages")
    .withIndex("by_exam_id_and_seq", (q) => q.eq("exam_id", examId))
    .order("asc")
    .collect();
}

export async function lastMessageSeq(db: DatabaseReader, examId: string): Promise<number> {
  const lastMessage = await db
    .query("exam_messages")
    .withIndex("by_exam_id_and_seq", (q) => q.eq("exam_id", examId))
    .order("desc")
    .first();
  return lastMessage?.seq ?? 0;
}
