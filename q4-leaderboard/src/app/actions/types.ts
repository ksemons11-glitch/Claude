export type FormState =
  | {
      error?: string;
      success?: string;
      fields?: Record<string, string>;
      /** Set when a participant tried to lower the cumulative value — enables the correction request. */
      correctionFor?: number;
    }
  | undefined;
