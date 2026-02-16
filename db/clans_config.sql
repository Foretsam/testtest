Create TABLE
  IF NOT EXISTS clans (
    tag VARCHAR(15) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    leader_id BIGINT,
    prefix VARCHAR(5),
    emoji VARCHAR(50),
    msg TEXT,
    questions TEXT,
    requirements VARCHAR(20),
    role_id BIGINT,
    gk_role_id BIGINT,
    clan_type VARCHAR(20),
    recruitment BOOLEAN DEFAULT FALSE,
    chat_channel_id BIGINT,
    announcment_id BIGINT,
    check_hero_max INT DEFAULT NULL,
    check_hero_sum INT DEFAULT NULL
  );