import { db } from "@/lib/db";

export const settingsRepository = {
  list() {
    return db.setting.findMany({
      orderBy: {
        key: "asc",
      },
    });
  },

  async ensureDefaults(defaults: Array<{ key: string; value: unknown; description: string }>) {
    await Promise.all(
      defaults.map((setting) =>
        db.setting.upsert({
          where: { key: setting.key },
          update: {},
          create: {
            key: setting.key,
            value: setting.value as never,
            description: setting.description,
          },
        }),
      ),
    );
  },
};
