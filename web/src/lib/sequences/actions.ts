"use server";

/**
 * Getting a sequence in without leaving the page.
 *
 * Server actions rather than route handlers, so the browser never learns the
 * API's address and the NCBI contact details never reach it either.
 *
 * Neither of these needs an account. Somebody deciding whether PCRStudio is
 * worth signing up for should be able to watch it resolve an accession first.
 */

import { api, PcrStudioError } from "@/lib/api";
import type { Aligned, ConsensusResult, FetchAnswer } from "@/lib/api/types";

export interface FetchState {
  answer?: FetchAnswer;
  error?: string;
}

export interface AlignState {
  aligned?: Aligned;
  error?: string;
}

export interface ConsensusState {
  result?: ConsensusResult;
  error?: string;
}

function describe(cause: unknown): string {
  if (cause instanceof PcrStudioError || cause instanceof Error) return cause.message;
  return "The lookup could not be completed.";
}

export async function fetchAccessionAction(accessions: string): Promise<FetchState> {
  if (!accessions.trim()) return { error: "Type an accession, like NM_000546.6." };

  try {
    return { answer: await api.fetchSequences(accessions) };
  } catch (cause) {
    return { error: describe(cause) };
  }
}

export async function alignAction(fasta: string): Promise<AlignState> {
  try {
    return { aligned: await api.alignSequences(fasta) };
  } catch (cause) {
    return { error: describe(cause) };
  }
}

export async function consensusAction(fasta: string): Promise<ConsensusState> {
  try {
    return { result: await api.consensus(fasta) };
  } catch (cause) {
    return { error: describe(cause) };
  }
}
