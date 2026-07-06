-- AlterTable
ALTER TABLE "User"
ADD COLUMN "mapsApiKeyCipher" TEXT,
ADD COLUMN "mapsApiKeyIv" TEXT,
ADD COLUMN "mapsApiKeyTag" TEXT;

