-- Initialising the schema generated from beer_loss.storage.metadata.
CREATE TABLE IF NOT EXISTS beer_loss_records (
	id VARCHAR(36) NOT NULL, 
	request_key VARCHAR(36) NOT NULL, 
	natural_key VARCHAR(260), 
	resource_key VARCHAR(120), 
	kind VARCHAR(24) NOT NULL, 
	site VARCHAR(32) NOT NULL, 
	occurred_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	production_date DATE NOT NULL, 
	shift VARCHAR(16) NOT NULL, 
	logged_by VARCHAR(120) NOT NULL, 
	payload JSON NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	voided BOOLEAN NOT NULL, 
	void_reason TEXT, 
	voided_by VARCHAR(120), 
	voided_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (request_key), 
	UNIQUE (natural_key), 
	UNIQUE (resource_key)
);
CREATE INDEX IF NOT EXISTS ix_beer_loss_site_time ON beer_loss_records (site, occurred_at);
