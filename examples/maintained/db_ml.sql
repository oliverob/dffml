DROP TABLE IF EXISTS `ml_data`;
CREATE TABLE IF NOT EXISTS `ml_data` (
  `key` VARCHAR(1000) PRIMARY KEY NOT NULL,
  `json` text
);