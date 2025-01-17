#!/usr/bin/env perl
#------------------------------------------------------------------------------
#
# PgCluu - PostgreSQL monitoring tool with statistics collector and grapher
#
# This program is open source, licensed under the PostgreSQL license.
# For license terms, see the LICENSE file.
#
# Author: Gilles Darold
# Copyright: (C) 2012-2015 Gilles Darold - All rights reserved.
#------------------------------------------------------------------------------
use vars qw($VERSION $PROGRAM);

use strict qw(vars);
use warnings;

use CGI;
use IO::File;
use Getopt::Long qw(:config bundling no_ignore_case_always);
use File::Basename;
use Time::Local 'timegm_nocheck';
use POSIX qw(locale_h sys_wait_h ceil);
setlocale(LC_ALL, 'C');
use Storable qw(store_fd fd_retrieve);

$VERSION = '3.0';
$PROGRAM = 'pgCluu';

my $SADF_PROG       = '/usr/bin/sadf';
my $DISABLE_SAR     = 0;
my $HTML            = '';
my @INCLUDE_DB      = ();
my @INCLUDE_TB      = ();
my @INCLUDE_DEV     = ();
my @INCLUDE_IFACE   = ();
my $IMG_FORMAT      = 'png';
my $FH              = undef;
my %DEVFH           = ();
my $IDX             = 1;
my $HELP            = 0;
my $SHOW_VER        = 0;
my $DEBUG           = 0;
my $NUMBER_CPU      = 0;
my $TIMEZONE        = '00';
my $STATS_TIMEZONE  = '00';
my $REVERT_DATE     = 0;
my $FROM_SA_FILE    = 0;
my $SADC_INPUT_FILE = '';
my $SAR_INPUT_FILE  = '';
our @DEVICE_LIST    = ();
our @IFACE_LIST     = ();
my @GRAPH_COLORS    = ('#6e9dc9', '#f4ab3a', '#ac7fa8', '#8dbd0f'); 
my $ZCAT_PROG       = '/bin/zcat';
my $INTERVAL        = 1;
my $CACHE = 0;

my %RELKIND = (
	'r' => 'tables',
	'i' => 'indexes',
	'S' => 'sequences',
	'v' => 'views',
	'c' => 'composite types',
	't' => 'toast tables'
);
my $TOP_STAT       = 10;

# Global variables that need to be saved in incremental mode
our %OVERALL_STATS   = ();
our %global_infos = ();
our @global_databases = ();
our @global_tbspnames = ();
our %all_stat_database = ();
our %all_stat_database_conflicts = ();
our %all_database_size = ();
our %all_tablespace_size = ();
our %all_vacuum_stat = ();
our %all_stat_user_tables = ();
our %all_stat_user_indexes = ();
our %all_statio_user_tables = ();
our %all_relation_buffercache = ();
our %all_statio_all_indexes = ();
our %all_xlog_stat = ();
our %all_stat_bgwriter = ();
our %all_stat_connections = ();
our %all_stat_user_functions = ();
our %all_stat_replication = ();
our %all_pgbouncer_stats = ();
our %all_pgbouncer_ini = ();
our %all_pgbouncer_req_stats = ();
our %all_class_size = ();
our %all_stat_locks = ();
our %all_stat_unused_indexes = ();
our %all_stat_redundant_indexes = ();
our %all_stat_missing_fkindexes = ();
our %all_postgresql_conf = ();
our %all_recovery_conf = ();
our %all_postgresql_auto_conf = ();
our %pg_hba_conf = ();
our %pg_ident_conf = ();
our %all_settings = ();
our %all_db_role_setting = ();
our %all_database_buffercache = ();
our %all_database_usagecount = ();
our %all_database_isdirty = ();
our %all_stat_archiver = ();
our %all_stat_statements = ();

# Names of the variables that need to be saved as binary file
our @pg_to_be_stored = (
	'global_infos',
	'global_databases',
	'global_tbspnames',
	'all_stat_database',
	'all_stat_database_conflicts',
	'all_database_size',
	'all_tablespace_size',
	'all_vacuum_stat',
	'all_stat_user_tables',
	'all_stat_user_indexes',
	'all_statio_user_tables',
	'all_relation_buffercache',
	'all_statio_all_indexes',
	'all_xlog_stat',
	'all_stat_bgwriter',
	'all_stat_connections',
	'all_stat_user_functions',
	'all_stat_replication',
	'all_pgbouncer_stats',
	'all_pgbouncer_ini',
	'all_pgbouncer_req_stats',
	'all_class_size',
	'all_stat_locks',
	'all_stat_unused_indexes',
	'all_stat_redundant_indexes',
	'all_stat_missing_fkindexes',
	'all_postgresql_conf',
	'all_recovery_conf',
	'all_postgresql_auto_conf',
	'pg_hba_conf',
	'pg_ident_conf',
	'all_settings',
	'all_db_role_setting',
	'all_database_buffercache',
	'all_database_usagecount',
	'all_database_isdirty',
	'all_stat_archiver',
	'all_stat_statements',
);

# Names of sar variables that need to be saved as binary file
our %sar_cpu_stat = ();
our %sar_load_stat = ();
our %sar_process_stat = ();
our %sar_context_stat = ();
our %sar_memory_stat = ();
our %sar_swap_stat = ();
our %sar_pageswap_stat = ();
our %sar_block_stat = ();
our %sar_srvtime_stat = ();
our %sar_rw_devices_stat = ();
our %sar_util_devices_stat = ();
our %sar_networks_stat = ();
our %sar_neterror_stat = ();

our @sar_to_be_stored = (
	'global_infos',
	'sar_cpu_stat',
	'sar_load_stat',
	'sar_process_stat',
	'sar_context_stat',
	'sar_memory_stat',
	'sar_swap_stat',
	'sar_pageswap_stat',
	'sar_block_stat',
	'sar_srvtime_stat',
	'sar_rw_devices_stat',
	'sar_util_devices_stat',
	'sar_networks_stat',
	'sar_neterror_stat'
);

our %sysinfo   = (); # Hash used to store system information

# Store default timestamp
my ($o_sec, $o_min, $o_hour, $o_day, $o_month, $o_year) = (0,0,0,0,0,0);
my ($e_sec, $e_min, $e_hour, $e_day, $e_month, $e_year) = (0,0,0,0,0,0);

# Variable use to construct the date part of the sar output
# it is set with de date found in sar file kernel header.
my $sar_year  = '';
my $sar_month = '';
my $sar_day   = '';


# Charset used in the html output
my $charset = 'utf-8';

# Statistics files to use with report
my %DB_GRAPH_INFOS = (
	'pg_stat_database.csv' => {
		'1' => {
			'name' =>  'database-backends',
			'title' => 'Connections on %s database',
			'description' => 'Number of clients connected to a database.',
			'ylabel' => 'Connections',
			'legends' => ['backends'],
		},
		'2' => {
			'name' =>  'database-read_write_query',
			'title' => 'Affected tuples per operation on %s database',
			'ylabel' => 'Tuples',
			'description' => 'Affected rows on databases grouped by statement family.',
		},
		'3' => {
			'name' =>  'database-cache_ratio',
			'title' => 'Cache hit/miss ratio on %s database',
			'description' => 'Per database cache hit/miss ratio.',
			'ylabel' => 'Blocks per second',
			'legends' => ['Cache hit','Cache miss','hit/miss ratio'],
			'y2label' => 'Percentage',
		},
		'4' => {
			'name' =>  'database-commits_rollbacks',
			'title' => 'Commits/Rollbacks per second on %s database',
			'description' => 'Number of commits / rollbacks per second and number of backends per database.',
			'ylabel' => 'Transaction/sec',
			'legends' => ['commit','rollback','backends'],
			'y2label' => 'Number of backend',
		},
		'5' => {
			'name' =>  'database-write_ratio',
			'title' => 'Write ratio on %s database',
			'description' => 'Write ratio on databases excluding templates and postgres.',
			'ylabel' => 'Write queries per second',
			'legends' => ['Insert','Update','Delete'],
		},
		'6' => {
			'name' =>  'database-read_ratio',
			'title' => 'Read tuples on %s database',
			'description' => 'Show entries returned from the index and live rows fetched from the tables. The latter will be less if any dead or not-yet-committed rows are fetched using the index.',
			'ylabel' => 'Tuples per second',
			'legends' => ['Table (returned)','Index (fetched)'],
		},
		'7' => {
			'name' =>  'database-deadlocks',
			'title' => 'Number of deadlocks on %s database',
			'description' => 'Number of deadlocks detected in this database.',
			'ylabel' => 'Number of deadlocks',
			'legends' => ['deadlocks'],
		},
		'8' => {
			'name' =>  'database-canceled_queries',
			'title' => 'Number of canceled queries on %s database',
			'description' => 'Number of queries canceled due to conflicts with recovery in this database. [Conflicts occur only on standby servers]',
			'ylabel' => 'Number of queries canceled',
			'legends' => ['conflicts'],
		},
		'9' => {
			'name' =>  'database-temporary_files',
			'title' => 'Number of temporary files on %s database',
			'description' => 'Number of temporary files created by queries per database.',
			'ylabel' => 'Number of files',
			'legends' => ['temporary files'],
		},
		'10' => {
			'name' =>  'database-temporary_bytes',
			'title' => 'Size of temporary data on %s database',
			'description' => 'Amount of data written to temporary files created by queries per database.',
			'ylabel' => 'Size per seconde',
			'legends' => ['temporary data'],
		},
	},
	'pg_stat_database_conflicts.csv' =>  {
		'1' => {
			'name' =>  'database-conflicts',
			'title' => 'Conflicts per type on %s database',
			'description' => 'Per database statistics about query cancels occurring due to conflicts with recovery on standby servers.',
		},
	},
	'pg_database_size.csv' => {
		'1' => {
			'name' =>  'database-size',
			'title' => 'Size of %s database',
			'description' => 'Database sizes.',
			'ylabel' => 'Size',
			'legends' => ['size'],
			'active' => 1,
		},
	},
	'pg_tablespace_size.csv' => {
		'1' => {
			'name' =>  'tablespace-size',
			'title' => 'Size of %s tablespace',
			'description' => 'Tablespace size and location.',
			'ylabel' => 'Size',
			'legends' => ['size'],
		},
	},
	'pg_stat_bgwriter.csv' => {
		'1' => {
			'name' => 'database-checkpoints',
			'title' => 'checkpoints counter stats',
			'description' => 'Background writer statistics on checkpoints. Checkpoints timed is checkpoints issued because of checkpoint_timeout and checkpoints request is checkpoint issued by request.',
			'ylabel' => 'Number of checkpoints',
			'legends' => ['checkpoints timed','checkpoints requests'],
		},
		'2' => {
			'name' =>  'database-bgwriter',
			'title' => 'background writer clean stats',
			'description' => 'Background writer cache cleaning statistics by checkpoints, lru and backends.',
			'ylabel' => 'Buffers per second',
			'legends' => ['checkpoint buffers','clean buffers','backend buffers'],
		},
		'3' => {
			'name' =>  'database-bgwriter_count',
			'title' => 'background writer count stats',
			'description' => 'Background writer counter stats. Max written clean reports the number of times the background writer stopped a cleaning scan because it had written too many buffers. Buffers backend fsync reports the number of times a backend had to execute its own fsync call (normally the background writer handles those even when the backend does its own write).',
			'ylabel' => 'Times per second',
			'legends' => ['maxwritten clean','buffers backend fsync'],
		},
		'4' => {
			'name' => 'database-checkpoints_time',
			'title' => 'checkpoints write stats',
			'description' => 'Background writer statistics on checkpoints. Checkpoint write time reports the total amount of time that has been spent in the portion of checkpoint processing where files are written to disk. Checkpoint sync time reports the total amount of time that has been spent in the portion of checkpoint processing where files are synchronized to disk.',
			'ylabel' => 'mDuration',
			'legends' => ['checkpoint write time','checkpoint sync time'],
		},
	},
	'pg_stat_connections.csv' => {
		'1' => {
			'name' =>  'database-connections',
			'title' => 'Connections by type on %s database',
			'description' => 'Connections by type including idle ones.',
			'ylabel' => 'Number of connections',
			'legends' => ['Active','Idle','Idle in xact', 'Waiting for a lock'],
		},
	},
	'pg_stat_user_functions.csv' => {
		'1' => {
			'name' =>  'database-functions',
			'title' => 'Functions statistics on database %s',
			'description' => 'Statistics about executions times and duration of user functions.',
			'ylabel' => 'Duration',
			'active' => 1,
			'legends' => ['total time','self time'],
			'menu' => 'Functions statistics',
		},
	},
	'pg_stat_all_tables.csv' => {
		'1' => {
			'name' =>  'table-indexes',
			'title' => 'Sequencial vs Index scan on %s',
			'description' => 'Number of sequential scan versus index scan per table during the audit period.',
			'ylabel' => 'Number per second',
			'legends' => ['sequential scan','index scan','% index scan ratio'],
			'y2label' => 'Percent',
			'active' => 1,
			'menu' => 'Index scan ratio',
		},
		'2' => {
			'name' =>  'table-vacuums-analyzes',
			'title' => 'Analyze/vacuums count on %s',
			'description' => 'Number of analyze, autoanalyze, vacuum and autovacuum count per table during the audit period.',
			'ylabel' => 'Number',
			'legends' => ['Analyze','Autoanalyze','Vacuum','Autovacuum'],
			'active' => 1,
			'menu' => 'Vacuums/analyzes',
		},
		'3' => {
			'name' =>  'table-query-tuples',
			'title' => 'Insert/update/delete and hot update tuples on %s',
			'description' => 'Number of insert/update/delete and hot update tuples count per table during the audit period.',
			'ylabel' => 'Number per second',
			'legends' => ['Insert','Update','Delete','Hot Update'],
			'active' => 1,
			'menu' => 'insert/update/delete',
		},
		'4' => {
			'name' =>  'table-kind-tuples',
			'title' => 'Live vs dead tuples on %s',
			'description' => 'Number of live and dead tuples per table at end of the audit period.',
			'ylabel' => 'Number',
			'legends' => ['Live','Dead','% Bloat ratio'],
			'y2label' => 'Percent',
			'active' => 1,
			'menu' => 'Live vs dead tuples',
		},
	},
	'pg_statio_all_tables.csv' => {
		'1' => {
			'name' =>  'statio-table',
			'title' => 'Statistics about I/O on %s',
			'description' => 'Number of disk blocks read from this table or all indexes on this table versus number of buffer hits in a table or all indexes of this table.',
			'ylabel' => 'Number per second',
			'legends' => ['heap_blks_read','heap_blks_hit','idx_blks_read','idx_blks_hit'],
			'active' => 1,
			'menu' => 'Tables I/O stats',
		},
	},
	'pg_stat_all_indexes.csv' => {
		'1' => {
			'name' =>  'index-scan',
			'title' => 'Statistics about accesses to index %s',
			'description' => 'Number of index entries returned by index scans, and number of live table rows fetched by simple index scans using that index during the audit period.',
			'ylabel' => 'Number per second',
			'legends' => ['index scans initiated','index entries read','live table rows fetched'],
			'y2label' => 'Percent',
			'active' => 1,
			'menu' => 'Index read/fetch',
		},
	},
	'pg_statio_all_indexes.csv' => {
		'1' => {
			'name' =>  'statio-index',
			'title' => 'Statistics about I/O on %s',
			'description' => 'Number of disk blocks read from this index versus number of buffer hits in this index.',
			'ylabel' => 'Number per second',
			'legends' => ['idx_blks_read','idx_blks_hit'],
			'active' => 1,
			'menu' => 'Indexes I/O stats',
		},
	},
	'pg_stat_unused_indexes.csv' => {
		'1' => {
			'name' =>  'unused-index',
			'title' => 'Unused indexes on %s',
			'description' => 'List of indexes never used (idx_scan = 0).',
			'ylabel' => 'Number',
			'legends' => ['Unused index'],
			'active' => 1,
			'menu' => 'Unused Indexes',
		},
	},
	'pg_stat_redundant_indexes.csv' => {
		'1' => {
			'name' =>  'redundant-index',
			'title' => 'Redundant indexes on %s',
			'description' => 'List of useless indexes because they are redundant.',
			'ylabel' => 'Number',
			'legends' => ['Redundant index'],
			'active' => 1,
			'menu' => 'Redundant indexes',
		},
	},
	'pg_stat_missing_fkindexes.csv' => {
		'1' => {
			'name' =>  'missing-index',
			'title' => 'Missing FK indexes on %s',
			'description' => 'List of DDL to create missing indexes on foreign keys.',
			'ylabel' => 'Number',
			'legends' => ['Missing index'],
			'active' => 1,
			'menu' => 'Missing indexes',
		},
	},
	'pg_xlog_stat.csv' => {
		'1' => {
			'name' =>  'database-xlog_files',
			'title' => 'WAL files',
			'description' => 'Number of WAL file in the xlog directory.',
			'ylabel' => 'Number of files',
			'legends' => ['total xlog'],
		},
	},
	'pg_stat_replication.csv' => {
		'1' => {
			'name' =>  'database-xlog',
			'title' => 'Xlog written',
			'description' => 'Number of xlog data written per second.',
			'ylabel' => 'Size per second',
			'legends' => ['written'],
		},
		'2' => {
			'name' =>  'database-replication',
			'title' => 'Replication lag with %s',
			'description' => 'Lag of replication between primary and secondary servers.',
			'ylabel' => 'Lag sizes',
			'legends' => ['Sent','Write','Replay'],
		},
	},
	'pgbouncer_stats.csv' => {
		'1' => {
			'name' =>  'pgbouncer-connections',
			'title' => 'pgbouncer connections statistics on pool %s',
			'description' => 'Number of active/waiting clients, active/idle/used server connections and maximum wait duration for client connections in each pgbouncer pool.',
			'ylabel' => 'Number of connexions',
			'legends' => ['Client active','Client waiting','Server active','Server idle','Server used','Clients wait time'],
			'y2label' => 'Duration',
		},
	},
	'pgbouncer_req_stats.csv' => {
		'1' => {
			'name' =>  'pgbouncer-duration',
			'title' => 'pgbouncer average queries duration on %s',
			'description' => 'Average queries duration in each pgbouncer pool.',
			'ylabel' => 'mDuration',
			'legends' => ['avg_query'],
		},
		'2' => {
			'name' =>  'pgbouncer-number',
			'title' => 'pgbouncer queries per second on %s',
			'description' => 'Number of queries per second in each pgbouncer pool.',
			'ylabel' => 'Number',
			'legends' => ['avg_req'],
		},
	},
	'pg_class_size.csv' => {
		'1' => {
			'name' =>  'table-size',
			'title' => 'Size of table %s',
			'description' => 'Disk space used by the table with number of rows at end of the audit.',
			'ylabel' => 'Size',
			'legends' => ['Object size', 'Number of tuples' ],
			'y2label' => 'Number',
			'active' => 1,
			'menu' => 'Size and tuples',
		},
		'2' => {
			'name' =>  'index-size',
			'title' => 'Size of index %s',
			'description' => 'Disk space used by the index with number of rows at end of the audit.',
			'ylabel' => 'Size',
			'legends' => ['Object size', 'Number of tuples' ],
			'y2label' => 'Number',
			'active' => 1,
			'menu' => 'Size and tuples',
		},
	},
	'pg_stat_locks.csv' => {
		'1' => {
			'name' =>  'database-lock-types',
			'title' => 'Types of locks on %s database',
			'description' => 'Number of locks per type in a database. Type of the lockable object: relation, extend, page, tuple, transactionid, virtualxid, object, userlock, or advisory.',
			'ylabel' => 'Number',
			'legends' => [],
			'active' => 1,
		},
		'2' => {
			'name' =>  'database-lock-modes',
			'title' => 'Modes of locks on %s database',
			'description' => 'Number of locks per lock mode held or desired by all process.',
			'ylabel' => 'Number',
			'legends' => [],
			'active' => 1,
		},
		'3' => {
			'name' =>  'database-lock-granted',
			'title' => 'Granted locks on %s database',
			'description' => 'Number of locks held (granted) or awaited (waiting).',
			'ylabel' => 'Number',
			'legends' => [],
			'active' => 1,
		},
	},
	'postgresql.conf' => {
		'1' => {
			'name' =>  'database-pgconf',
			'title' => 'PostgreSQL configuration',
			'description' => 'Configuration directives and values defined in file postgresql.conf.',
			'ylabel' => 'Number',
			'legends' => ['Settings'],
			'active' => 1,
			'menu' => 'PostgreSQL configuration',
		},
	},
	'postgresql.auto.conf' => {
		'1' => {
			'name' =>  'database-alterconf',
			'title' => 'PostgreSQL system altered configuration',
			'description' => 'Configuration directives and values defined using ALTER SYSTEM.',
			'ylabel' => 'Number',
			'legends' => ['Settings'],
			'active' => 1,
			'menu' => 'PostgreSQL system altered configuration',
		},
	},
	'recovery.conf' => {
		'1' => {
			'name' =>  'database-recoveryconf',
			'title' => 'PostgreSQL recovery configuration',
			'description' => 'Configuration directives and values defined in file recovery.conf.',
			'ylabel' => 'Number',
			'legends' => ['Settings'],
			'active' => 1,
			'menu' => 'PostgreSQL recovery configuration',
		},
	},
	'pg_hba.conf' => {
		'1' => {
			'name' =>  'database-pghba',
			'title' => 'PostgreSQL authorization',
			'description' => 'Client authentication controlled by pg_hba.conf configuration file.',
			'ylabel' => 'Number',
			'legends' => ['Setting','Value'],
			'active' => 1,
			'menu' => 'PostgreSQL authorization',
		},
	},
	'pg_ident.conf' => {
		'1' => {
			'name' =>  'database-pgident',
			'title' => 'PostgreSQL User Name Maps',
			'description' => 'Different operating system user / database user mappings might be needed for different connections. They are defined in file pg_ident.conf.',
			'ylabel' => 'Number',
			'legends' => ['Setting','Value'],
			'active' => 1,
			'menu' => 'User Name Maps',
		},
	},
	'pg_settings.csv' => {
		'1' => {
			'name' =>  'database-settings',
			'title' => 'PostgreSQL Settings',
			'description' => 'Configuration directives and values defined in pg_settings.',
			'ylabel' => 'Number',
			'legends' => ['Settings'],
			'active' => 1,
			'menu' => 'PostgreSQL settings',
		},
	},
	'pg_db_role_setting.csv' => {
		'1' => {
			'name' =>  'database-dbrolesetting',
			'title' => 'PostgreSQL Database/Roles Settings',
			'description' => 'Configuration directives and values defined with ALTER DATABASE and ALTER ROLE.',
			'ylabel' => 'Number',
			'legends' => ['Settings'],
			'active' => 1,
			'menu' => 'Database/Roles settings',
		},
	},
	'pgbouncer.ini' => {
		'1' => {
			'name' =>  'database-pgbouncer',
			'title' => 'Pgbouncer configuration',
			'description' => 'Configuration directives and values defined in file pgbouncer.ini.',
			'ylabel' => 'Number',
			'legends' => ['Setting','Value'],
			'active' => 1,
			'menu' => 'Pgbouncer settings',
		},
	},
	'pg_database_buffercache.csv' => {
		'1' => {
			'name' =>  'database-buffersused',
			'title' => 'Shared buffers utilization per database',
			'description' => 'Show statistics about percentage of shared buffers used per database.',
			'ylabel' => 'Percent',
			'legends' => [],
			'active' => 1,
			'menu' => 'Shared buffers utilization',
		},
		'2' => {
			'name' =>  'database-databaseloaded',
			'title' => 'Percentage of each databases loaded in shared buffers',
			'description' => 'Show statistics about percentage of each database loaded in shared buffers.',
			'ylabel' => 'Percent',
			'legends' => [],
			'menu' => 'Databases in shared buffers',
		},
	},
	'pg_database_usagecount.csv' => {
		'1' => {
			'name' =>  'database-usagecount',
			'title' => 'Shared buffers usagecount distribution',
			'description' => 'Show statistics about usagecount distribution in shared buffers.',
			'ylabel' => 'Percent',
			'legends' => [],
			'menu' => 'Usagecount utilization',
			'active' => 1,
		},
	},
	'pg_database_isdirty.csv' => {
		'1' => {
			'name' =>  'database-isdirty',
			'title' => 'Dirty shared buffers usagecount distribution',
			'description' => 'Show statistics about usagecount distribution in dirty shared buffers.',
			'ylabel' => 'Percent',
			'legends' => [],
			'menu' => 'Dirty Usagecount',
			'active' => 1,
		},
	},
	'pg_relation_buffercache.csv' => {
		'1' => {
			'name' =>  'buffercache-relation',
			'title' => 'Statistics about cache utilization for %s database',
			'description' => 'Number of shared buffers/pages used by a relation.',
			'ylabel' => 'Number',
			'legends' => ['buffers'],
			'active' => 1,
			'menu' => 'Buffercache per relation',
		},
		'2' => {
			'name' =>  'statio-buffercache',
			'title' => 'Statistics about cache utilization %s relation',
			'description' => 'Number of buffers loaded in cache for a relation and the percentage of the relation loaded.',
			'ylabel' => 'Number',
			'y2label' => 'percent',
			'legends' => ['buffered','relation %'],
			'menu' => 'Buffer I/O per relation',
		},
	},
	'pg_stat_archiver.csv' => {
		'1' => {
			'name' =>  'database-archive',
			'title' => 'Statistics about archiver',
			'description' => 'Number of WAL files archived with number of failure.',
			'ylabel' => 'Number',
			'legends' => ['archived count', 'failed count'],
			'active' => 1,
			'menu' => 'Archiving',
		}
	},
	'pg_stat_statements.csv' => {
		'1' => {
			'name' =>  'database-queries',
			'title' => 'Statistics about statements',
			'description' => 'Top N statistics about slowest or most used queries.',
			'ylabel' => 'Number',
			'legends' => ['queries'],
			'active' => 1,
			'menu' => 'Statements statistics',
		}
	},
);

my %SAR_GRAPH_INFOS = (
	'1' => {
		'name' =>  'system-cpu',
		'title' => 'CPU %s utilization',
		'description' => 'Percentage of CPU utilization that occurred while executing at the system level (kernel), the user level (application) and the percentage of time that the CPU or CPUs were idle during which the system had an outstanding disk I/O request.',
		'ylabel' => 'Percentage',
		'legends' => ['Total','System','User','Iowait'],
		'active' => 1,
	},
	'2' => {
		'name' =>  'system-load',
		'title' => 'System load',
		'description' => 'System  load average for the last minute, the past 5 and 15 minutes. The load average is calculated as the average number of runnable or running tasks (R state), and the number of tasks in uninterruptible sleep (D state) over the specified interval.',
		'ylabel' => 'Process load',
		'legends' => ['ldavg-1','ldavg-5','ldavg-15'],
	},
	'3' => {
		'name' =>  'system-process',
		'title' => 'Number of process',
		'description' => 'Number of tasks in the task list.',
		'ylabel' => 'Number of process',
		'legends' => ['plist-sz'],
	},
	'4' => {
		'name' =>  'system-memory',
		'title' => 'System memory utilization',
		'description' => 'Amount of memory used to cache data or as buffers by the kernel and free memory available.',
		'ylabel' => 'Memory size',
		'legends' => ['cached','buffers','memfree'],
	},
	'5' => {
		'name' =>  'system-swap',
		'title' => 'Swap In/Out (pages/seconds)',
		'description' => 'Total number of swap pages the system brought in/out per second. The page size usually is 4096 bytes.',
		'ylabel' => 'Pages/second',
		'legends' => ['pswpin/s','pswpout/s'],
	},
	'6' => {
		'name' =>  'system-block',
		'title' => 'Block In/Out (blocks/seconds)',
		'description' => 'Total amount of data read/write from the devices in blocks per second. Blocks are equivalent to sectors and therefore have a size of 512 bytes.',
		'ylabel' => 'Block per second',
		'legends' => ['bread/s','bwrtn/s'],
	},
	'7' => {
		'name' =>  'system-rwdevice',
		'title' => 'Data read/write on device %s',
		'description' => 'Number of bytes read/write from/to the device..',
		'ylabel' => 'Size Read/Written per second',
		'legends' => ['Read', 'Write'],
	},
	'8' => {
		'name' =>  'system-cpudevice',
		'title' => 'CPU utilization on device %s',
		'description' => 'Percentage of CPU time during which I/O requests were issued to the device (bandwidth utilization for the device). Device saturation occurs when this value is close to 100%.',
		'ylabel' => 'Percentage of CPU',
		'legends' => ['cpu used'],
	},
	'9' => {
		'name' =>  'system-srvtime',
		'title' => 'Average service/wait time for I/O requests on device %s',
		'description' => 'The average service time (in milliseconds) for I/O requests that were issued to the device.',
		'ylabel' => 'Milliseconds',
		'legends' => ['svctm','await'],
	},
	'10' => {
		'name' =>  'system-runqueue',
		'title' => 'Run queue length',
		'description' => 'Number of tasks waiting for run time.',
		'ylabel' => 'Run queue length',
		'legends' => ['runq-sz'],
	},
	'11' => {
		'name' => 'system-page',
		'title' => 'System cache statistics',
		'description' => 'Total number of kilobytes the system paged in/out from/to disk per second, and number of major faults the system has made per second, those which have required loading a memory page from disk.',
		'ylabel' => 'Size paged',
		'y2label' => 'Number of faults',
		'legends' => [ 'pgpgin/s', 'pgpgout/s', 'page faults/s' ],
	},
	'12' => {
		'name' => 'network-utilization',
		'title' => 'Network utilization on interface %s',
		'description' => 'Report statistics from the network devices utilization.',
		'ylabel' => 'Size per second',
		'legends' => ['received (rx)', 'transmitted (tx)' ],
	},
	'13' => {
		'name' => 'network-error',
		'title' => 'Network errors on interface %s',
		'description' => 'Report statistics on failures from the network device. Number of bad packets received,  number of errors that happened while transmitting packets, and number of collisions that happened per second while transmitting packets.',
		'ylabel' => 'Number per second',
		'legends' => ['rx errors', 'tx errors', 'collisions' ],
	},
	'14' => {
		'name' =>  'system-cswch',
		'title' => 'Context switches',
		'description' => 'Total number of context switches per second.',
		'ylabel' => 'Context switches',
		'legends' => ['cswch/s'],
	},
	'15' => {
		'name' =>  'system-pcrea',
		'title' => 'Tasks created',
		'description' => 'Total number of tasks created per second.',
		'ylabel' => 'Tasks',
		'legends' => ['proc/s'],
	},
	'16' => {
		'name' =>  'system-tps',
		'title' => 'Total number of transfers per second',
		'description' => 'Total number of transfers per second that were issued to physical devices. A transfer is an I/O request to a physical device. Multiple logical requests can be combined into a single I/O request to the device. A transfer is of indeterminate size.',
		'ylabel' => 'Transfers per second',
		'legends' => ['tps','rtps','wtps'],
	},
	'17' => {
		'name' =>  'system-tpsdevice',
		'title' => 'Transfert per second on device %s',
		'description' => 'Number of transfers per second that were issued to the device, multiple logical requests can be combined into a single I/O request to the device (a transfer is of indeterminate size).',
		'ylabel' => 'Number of transfers per second',
		'legends' => ['Tps'],
	},

);

# Set CGI handle and retrieve current params states
my $cgi = new CGI;
my $SCRIPT_NAME = $cgi->url() || '';
my $ACTION = $cgi->param('action') || 'home';
my $DATABASE = $cgi->param('db') || '';
my $DEVICE = $cgi->param('dev') || '';
my $BEGIN = $cgi->param('start') || '';
my $END = $cgi->param('end') || '';

my $REAL_ACTION = $ACTION || '';
$REAL_ACTION =~ s/^cluster/database/;
my $ID_ACTION = -1;

my $src_base = '';
my $INPUT_DIR = '';
my $RSC_BASE = '.';
my @database_list = ();

sub read_conf
{
	# Defined the backward level where ressources files are stored
	$src_base = '';
	#$INPUT_DIR = '/data/file_data/data/data_pgcluu_demo';
	$INPUT_DIR = '/home/git/pgcluu/test2';
	$RSC_BASE = '.';

	@INCLUDE_DB = ('[^p].*');

        #$BEGIN = '2014-02-27 13:00:00';
        #$END = '2014-02-27 14:00:00';

	if (!$BEGIN) {
#		$BEGIN = '2015-06-11 19:00:00';
#		$END = '2015-06-11 22:00:00';
	}

	my @tbs_opts;
	foreach (@tbs_opts) {
		push(@INCLUDE_TB, split(/[,]+/, $_));
	}
	my @net_opts;
	foreach (@net_opts) {
		push(@INCLUDE_IFACE, split(/[,]+/, $_));
	}

	# Check start/end date time
	if ($BEGIN) {
		if ($BEGIN =~ /^(\d{4})-(\d+)-(\d+) (\d+):(\d+)/) {
			$BEGIN = &timegm_nocheck($6, $5, $4, $3, $2 - 1, $1 - 1900) * 1000;
			$o_day = sprintf("%02d", $3);
			$o_month = sprintf("%02d", $2);
			$o_year = $1;
			$o_hour = sprintf("%02d", $4);
			$o_min = sprintf("%02d", $5);
			$o_sec = '00';
		} elsif ($BEGIN =~ /^(\d{4})-(\d+)-(\d+)$/) {
			$BEGIN = &timegm_nocheck(0, 0, 0, $3, $2 - 1, $1 - 1900) * 1000;
			$o_day = sprintf("%02d", $3);
			$o_month = sprintf("%02d", $2);
			$o_year = $1;
			$o_hour = '00';
			$o_min = '00';
			$o_sec = '00';
		} else {
			die "FATAL: bad format for begin datetime, should be yyyy-mm-dd hh:mm:ss\n";
		}
	}
	if ($END) {
		if ($END =~ /^(\d{4})-(\d+)-(\d+) (\d+):(\d+)$/) {
			$END = &timegm_nocheck($6, $5, $4, $3, $2 - 1, $1 - 1900) * 1000;
			$e_day = sprintf("%02d", $3);
			$e_month = sprintf("%02d", $2);
			$e_year = $1;
			$e_hour = sprintf("%02d", $4);
			$e_min = sprintf("%02d", $5);
			$e_sec = '59';
		} elsif ($END =~ /^(\d{4})-(\d+)-(\d+)$/) {
			$END = &timegm_nocheck(0, 0, 0, $3, $2 - 1, $1 - 1900) * 1000;
			$e_day = printf("%02d", 3);
			$e_month = sprintf("%02d", $2);
			$e_year = $1;
			$e_hour = '23';
			$e_min = '59';
			$e_sec = '59';
		} else {
			die "FATAL: bad format for ending datetime, should be yyyy-mm-dd hh:mm:ss\n";
		}
	}

}

&read_conf();

####
# Look into subdirectories to find daily and hourly data files.
####
my @WORK_DIRS = &get_data_directories();

if (!$o_year) {
	($o_sec, $o_min, $o_hour, $o_day, $o_month, $o_year) = localtime(time);
	$o_year += 1900;
	$o_month++;
}
if (!$e_year) {
	($e_sec, $e_min, $e_hour, $e_day, $e_month, $e_year) = localtime(time);
	$e_year += 1900;
	$e_month++;
}

####
# Start to look for devices and database to build the menu
####
foreach (my $dx = 0; $dx <= $#WORK_DIRS; $dx++) {
	my $in_dir = "$INPUT_DIR/$WORK_DIRS[$dx]";
	my ($sar_file, $sadc_file) = &set_sysstat_file($in_dir);
	@DEVICE_LIST = &get_device_list($sar_file, $sadc_file);
	@IFACE_LIST = &get_interface_list($sar_file, $sadc_file);
	last if ($#DEVICE_LIST >= 0);
}

# show last sysinfo collected
my $in_dir = $INPUT_DIR || '.';
$in_dir .= "/$WORK_DIRS[-1]" if ($#WORK_DIRS >= 0);
print STDERR "DEBUG: Looking for system information in directory $in_dir\n" if ($DEBUG);
if (-e "$in_dir/sys_cache.bin") {
	print STDERR "DEBUG: Loading system information from cache file $in_dir/sys_cache.bin\n" if ($DEBUG);
	&load_sys_binary($in_dir, "sys_cache.bin");
} elsif (-e "$in_dir/sysinfo.txt") {
	print STDERR "DEBUG: Loading system information from file $in_dir/sysinfo.txt\n" if ($DEBUG);
	%sysinfo = &read_sysinfo("$in_dir/sysinfo.txt");
	$sysinfo{RELEASE}{'name'} ||= 'unknown';
} elsif (-e "$in_dir/sysinfo.txt.gz") {
	print STDERR "DEBUG: Loading system information from file $in_dir/sysinfo.txt.gz\n" if ($DEBUG);
	%sysinfo = &read_sysinfo("$in_dir/sysinfo.txt.gz");
	$sysinfo{RELEASE}{'name'} ||= 'unknown';
}

# Set database list
foreach my $db (keys %{$sysinfo{EXTENSION}}) {
	push(@database_list, $db);
}

####
# Generate page header (common to all reports and include menu)
####
&html_header();

#### Show empty data
if ($#WORK_DIRS < 0) {
	&wrong_date_selection();
	&html_footer();
	exit 0;
}

#### Show about page and exit
if ($ACTION eq 'about') {
	&show_about();
	&html_footer();
	exit 0;
}

if ($ACTION eq 'sysinfo') {
	&show_sysinfo($in_dir);
	&html_footer();
	exit 0;
}


foreach (my $dx = 0; $dx <= $#WORK_DIRS; $dx++) {

	my $in_dir = "$INPUT_DIR/$WORK_DIRS[$dx]";

	# Check if we have binary file in the directory
	my @binfiles = ();
	if (-d "$in_dir") {
		opendir(IDIR, "$in_dir") || die "FATAL: can't opendir $in_dir: $!";
		@binfiles = grep { /^all_.*\.bin$/ } readdir(IDIR);
		closedir(IDIR);
	} else {
		# Input directory does not exists
		next;
	}

	# Set default sysstat file to read (binary or text format)
	# an extract the disk devices and network interfaces list
	# if there's no binary files
	if (($ACTION eq 'home') || ($ACTION =~ /^(system|device|network)-/)) {
		my $sar_file = '';
		my $sadc_file = '';
		if ($#binfiles < 0) {
			# Build sar statistics if a cache file is not present
			($sar_file, $sadc_file) = &set_sysstat_file($in_dir);
			@DEVICE_LIST = &get_device_list($sar_file, $sadc_file);
			@IFACE_LIST = &get_interface_list($sar_file, $sadc_file);
			if (-f "$sadc_file") {
				print STDERR "DEBUG: looking for sadc binary data file $sadc_file\n" if ($DEBUG);
				foreach my $id (sort keys %SAR_GRAPH_INFOS) {
					next if (($ACTION ne 'home') && ($REAL_ACTION ne $SAR_GRAPH_INFOS{$id}->{name}));
					&compute_sarstat_stats($sadc_file, %{$SAR_GRAPH_INFOS{$id}});
				}
			} elsif (-f "$sar_file") {
				print STDERR "DEBUG: looking for sar text data file $sar_file\n" if ($DEBUG);
				foreach my $id (sort keys %SAR_GRAPH_INFOS) {
					next if (($ACTION ne 'home') && ($REAL_ACTION ne $SAR_GRAPH_INFOS{$id}->{name}));
					&compute_sarfile_stats($sar_file, %{$SAR_GRAPH_INFOS{$id}});
				}
			}

		} else {

			#Load statistics from cache files
			@DEVICE_LIST = ();
			@IFACE_LIST = ();
			print STDERR "DEBUG: Loading Sar statistics from cache files $in_dir/*.bin\n" if ($DEBUG);
			&load_sar_binary($in_dir);
		}
	}

	if (($ACTION eq 'home') || ($ACTION eq 'database-info') || ($ACTION !~ /^(system|device|network)-/)) {

		if ($#binfiles == -1) {

			# Check if there is csv file in the input directory
			print STDERR "DEBUG: looking for CSV file into directory $in_dir/\n" if ($DEBUG);
			opendir(IDIR, "$in_dir") || die "FATAL: can't opendir $in_dir: $!";
			my @files = grep { /\.csv(\.gz)?$/ } readdir(IDIR);
			closedir(IDIR);
			if ($#files < 0) {
				die "FATAL: no csv file found in $in_dir";
			}

			# Detect interval from csv file
			if (-e "$in_dir/pg_stat_database.csv" && !-z "$in_dir/pg_stat_database.csv") {
				$INTERVAL = &detect_interval("$in_dir/pg_stat_database.csv");
			} elsif (-e "$in_dir/pg_stat_database.csv.gz" ) {
				$INTERVAL = &detect_interval("$in_dir/pg_stat_database.csv.gz");
			}
			print STDERR "DEBUG: autodetected interval value $INTERVAL\n" if ($DEBUG);

			# Loop over CSV files and graphics definition to generate reports
			print STDERR "DEBUG: Building PostgreSQL statistics From $ACTION CSV files\n" if ($DEBUG);
			foreach my $k (sort {$a cmp $b} keys %DB_GRAPH_INFOS) {
				my $to_be_proceed = 0;
				foreach my $n (keys %{$DB_GRAPH_INFOS{$k}}) {
					$to_be_proceed = 1, last if (($ACTION eq 'home') || ($ACTION eq 'database-info') || ($REAL_ACTION eq $DB_GRAPH_INFOS{$k}{$n}->{name}));
				}
				next if (!$to_be_proceed);
				if (-e "$in_dir/$k" && !-z "$in_dir/$k") {
					if (-e "$in_dir/$k" && !-z "$in_dir/$k") {
						&compute_postgresql_stat($in_dir, $k, $src_base, %{$DB_GRAPH_INFOS{$k}});
					}
				} elsif (-e "$in_dir/$k.gz" && !-z "$in_dir/$k.gz") {
					if (-e "$in_dir/$k.gz" && !-z "$in_dir/$k.gz") {
						&compute_postgresql_stat($in_dir, "$k.gz", $src_base, %{$DB_GRAPH_INFOS{$k}}); 
					}
				} elsif ($k =~ /_all_/) {
					my $f = $k;
					$f =~ s/_all_/_user_/;
					if (-e "$in_dir/$f" && !-z "$in_dir/$f") {
						&compute_postgresql_stat($in_dir, $f, $src_base, %{$DB_GRAPH_INFOS{$k}});
					} elsif (-e "$in_dir/$f.gz" && !-z "$in_dir/$f.gz") {
						&compute_postgresql_stat($in_dir, "$f.gz", $src_base, %{$DB_GRAPH_INFOS{$k}});
					}
				}
			}

		} else {

			# Load statistics from cache files
			print STDERR "DEBUG: Loading PostgreSQL statistics from $ACTION cache files from $in_dir\n" if ($DEBUG);
			&load_pg_binary($in_dir, $ACTION);

			# Try to find the interval related to these statistics
			if ($global_infos{interval}) {
				$INTERVAL = $global_infos{interval};
			} else {
				my $prev_val = 0;
				my $dt = 0;
				foreach $dt (sort {$a <=> $b} keys %all_stat_database) {
					if ($prev_val) {
						$dt = ($dt - $prev_val)/1000;
						last if ($dt > 0);
					}
					$prev_val = $dt;
				}
				if ( (length($dt) >= 2) && ($dt =~ /([1234])$/) ) {
					$dt -= $1;
				}
				$INTERVAL = $dt if ($dt);
			}

		}
	}

}


if (($ACTION ne 'home') || ($ACTION =~ /^(system|device|network)-/)) {

	# Build sar statistics graphs
	print STDERR "DEBUG: Building sar statistics reports\n" if ($DEBUG);
	foreach my $id (sort keys %SAR_GRAPH_INFOS) {
		next if (($ACTION ne 'home') && ($REAL_ACTION ne $SAR_GRAPH_INFOS{$id}->{name}));
		print STDERR "DEBUG: Reading sar statistics for $SAR_GRAPH_INFOS{$id}->{name}.\n" if ($DEBUG);
		&compute_sar_graph($src_base, %{$SAR_GRAPH_INFOS{$id}});
	}

}

if (($ACTION ne 'home') && ($ACTION ne 'database-info') && ($ACTION !~ /^(system|device|network)-/)) {

	# Loop over statistic in memory to generate reports
	print STDERR "DEBUG: Building PostgreSQL statistics reports\n" if ($DEBUG);

	# Try to limit report generation to stats that exists in memory.
	# The storage variable name are the same than the keys in DB_GRAPH_INFOS
	# minus some transformation.
	foreach my $k (sort {$a cmp $b} keys %DB_GRAPH_INFOS) {
		$ID_ACTION = -1;
		if ($ACTION ne 'home') {
			foreach my $n (keys %{$DB_GRAPH_INFOS{$k}}) {
				if ($REAL_ACTION eq $DB_GRAPH_INFOS{$k}{$n}->{name}) {
					$ID_ACTION = $n;
					last;
				}
			}
		} else {
			$ID_ACTION = 0;
		}
		next if ($ID_ACTION < 0);

		my $inmem = $k;
		$inmem =~ s/\.csv//;
		$inmem =~ s/\./_/g;
		$inmem =~ s/^pg_/all_/;
		if ($inmem eq 'pgbouncer_stats') {
			$inmem = 'all_pgbouncer_stats';
		}
		if (($inmem =~ /_conf/) && ($inmem !~ /^all/)) {
			$inmem = 'all_' . $inmem;
		}
		$inmem =~ s/_all_/_user_/;

		# Skip this report if there's no statistics loaded in memory
		next if ((scalar keys %{$inmem} == 0) && ($ID_ACTION == 0));
		print STDERR "DEBUG: Building report for $k (from memory \%$inmem)\n" if ($DEBUG);
		if ($k =~ /_all_/) {
			my $f = $k;
			$f =~ s/_all_/_user_/;
			&compute_postgresql_report($f, $src_base, %{$DB_GRAPH_INFOS{$k}}); 
		} else {
			&compute_postgresql_report($k, $src_base, %{$DB_GRAPH_INFOS{$k}}); 
		}
	}

}

# Show database general information
if ($ACTION eq 'database-info') {
	&write_database_info($DATABASE, $src_base);
}

#### Show home page information
if ($ACTION eq 'home') {
	&show_home();
}

####
# Add common HTML footer
####
&html_footer();

exit 0;

#----------------------------------------------------------------------------------

sub set_sysstat_file
{
	my $input_dir = shift;

	$input_dir ||= $INPUT_DIR;

	my $sar_file = '';
	my $sadc_file = '';
	if (!$SADC_INPUT_FILE && !$SAR_INPUT_FILE) {
		if (-f "$input_dir/sadc_stats.dat") {
			$sadc_file = "$input_dir/" . 'sadc_stats.dat';
		} elsif (-f "$input_dir/sar_stats.dat") {
			$sar_file = "$input_dir/" . 'sar_stats.dat';
		} elsif (-f "$input_dir/sar_stats.dat.gz") {
			$sar_file = "$input_dir/" . 'sar_stats.dat.gz';
		}
		if (!$sadc_file && !$sar_file) {
			print STDERR "WARNING: No sar data file found. Consider using -S or --disable-sar command\nline option or use -i / -I option to set the path to the data file.\nContinuing normally without reporting sar statistics.\n";
			$DISABLE_SAR = 1;
			return;
		}
	} else {
		$sadc_file = $SADC_INPUT_FILE;
		$sar_file = $SAR_INPUT_FILE;
	}

	# Verify that the sar data file exists.
	if ($sadc_file && !-f "$sadc_file") {
		print STDERR "ERROR: sar binary data file $sadc_file can't be found.\n";
		exit 1;
	}
	if ($sar_file && !-f "$sar_file") {
		print STDERR "ERROR: sar text data file $sar_file can't be found.\n";
		exit 1;
	}

	return ($sar_file, $sadc_file);
}

sub progress_bar
{
	my ( $got, $total, $width, $char ) = @_;
	$width ||= 25; $char ||= '=';
	my $num_width = length $total;
	sprintf("[%-${width}s] Parsed %${num_width}s bytes of %s (%0.2f%%)\r",
		$char x (($width-1)*$got/$total). '>',
		$got, $total, 100*$got/+$total);
}

sub is_compressed
{
	my $file = shift;

	return 1 if ($file =~ /\.gz/);

	return 0;
}

sub open_filehdl
{
	my $file = shift;

	my $curfh = new IO::File;
	if (!is_compressed("$file")) {
		$curfh->open("< $file") or die "FATAL: can't read file $file: $!\n";
	} else {
		$curfh->open("$ZCAT_PROG $file |") or die "FATAL: can't read pipe from command: $ZCAT_PROG $file, $!\n";
	}
	return $curfh;
}

sub detect_interval
{
	my $file = shift;

	my $dt = 0;
	my $prev_val = 0;

	if (!&is_compressed($file)) {
		if (!open(IN, "$file")) {
			die "FATAL: can't read file $file: $!\n";
		}
	} else {
		if (!open(IN, "$ZCAT_PROG $file |")) {
			die "FATAL: can't read pipe on command: $ZCAT_PROG $file, $!\n";
		}
	}
	while (<IN>) {
		my @data = split(/;/);
		next if ($data[0] !~ /^\d+/);
		$data[0] = &convert_time($data[0]);
		if (!$dt && $prev_val) {
			$dt = ($data[0] - $prev_val)/1000;
			last if ($dt > 0);
		}
		$prev_val = $data[0];
	}
	close(IN);

	if ( (length($dt) >= 2) && ($dt =~ /([1234])$/) ) {
		$dt -= $1;
	}

	return $dt || 1;
}

sub get_data_id
{
	my ($str, %data_info) = @_;

	foreach my $i (sort {$a <=> $b} keys %data_info) {
		if ($data_info{$i}->{name} eq $str) {
			return $i;
		}
	}
	return -1;
}

sub get_device_list
{
	my ($sar_file, $sadc_file) = @_;

	my @dev_list = ();

	if ($sadc_file && -f "$sadc_file") {

		my $command = "$SADF_PROG -t -P ALL -D $sadc_file -- -d -p";
		print STDERR "DEBUG: looking for device list using command $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		while (my $l = <IN>) {
			chomp($l);
			# hostname;interval;timestamp;DEV;tps;rd_sec/s;wr_sec/s;avgrq-sz;avgqu-sz;await;svctm;%util
			my @data = split(/;/, $l);
			next if ($data[2] !~ /^\d+/);
			if (!grep(m#^$data[3]$#, @dev_list)) {
				push(@dev_list, $data[3]);
			} else {
				last;
			}
		}
		close(IN);

	} elsif ($sar_file && -f "$sar_file") {

		print STDERR "DEBUG: looking for devices in sar file $sar_file\n" if ($DEBUG);
		# Load data from file
		if (!&is_compressed($sar_file)) {
			if (!open(IN, "$sar_file")) {
				die "FATAL: can't read input file $sar_file: $!\n";
			}
		} else {
			if (!open(IN, "$ZCAT_PROG $sar_file |")) {
				die "FATAL: can't read pipe from command: $ZCAT_PROG $sar_file, $!\n";
			}
		}
		my $type = '';
		my @headers = ();
		while (my $l = <IN>) {
			chomp($l);
			$l =~ s/\r//;
			# Skip kernel header part
			if ($l !~ /^\d+:\d+:\d+/) {
				next;
			}
			# Format timestamp when AM or PM is used
			$l =~ s/^(\d+:\d+:\d+)\s(AM|PM)/$1/;

			last if ($l =~ m#IFACE\s+#);
			if ($l =~ m#DEV\s+#) {
				if ($#headers == -1) {
					push(@headers, split(m#\s+#, $l));
					next;
				} else {
					last;
				}
			}
			# Empty line, maybe the end of a report
			if (($l eq '') && ($#headers >= 0)) {
				last;
			}
			# Get all values reported
			if ($#headers >= 0) {
				my @values = ();
				push(@values, split(m#\s+#, $l));
				last if ($#values != $#headers);
				if (!grep(m#^$values[1]$#, @dev_list)) {
					push(@dev_list, $values[1]);
				}
			}
		}
		close(IN);

	}

	return @dev_list;
}

sub get_interface_list
{
	my ($sar_file, $sadc_file) = @_;

	my @dev_list = ();

	if ($sadc_file && -f "$sadc_file") {

		my $command = "$SADF_PROG -t -P ALL -D $sadc_file -- -n DEV";
		print STDERR "DEBUG: looking for device list using command $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		while (my $l = <IN>) {
			chomp($l);
			# hostname;interval;timestamp;IFACE;rxpck/s;txpck/s;rxkB/s;txkB/s;rxcmp/s;txcmp/s;rxmcst/s
			my @data = split(/;/, $l);
			next if ($data[2] !~ /^\d+/);
			if (!grep(m#^$data[3]$#, @dev_list)) {
				push(@dev_list, $data[3]);
			} else {
				last;
			}
		}
		close(IN);

	} elsif ($sar_file && -f "$sar_file") {

		# Load data from file
		if (!&is_compressed($sar_file)) {
			if (!open(IN, "$sar_file")) {
				die "FATAL: can't read input file $sar_file: $!\n";
			}
		} else {
			if (!open(IN, "$ZCAT_PROG $sar_file |")) {
				die "FATAL: can't read input file $sar_file: $!\n";
			}
		}
		my $type = '';
		my @headers = ();
		while (my $l = <IN>) {
			chomp($l);
			$l =~ s/\r//;
			# Skip kernel header part
			if ($l !~ /^\d+:\d+:\d+/) {
				next;
			}
			# Format timestamp when AM or PM is used
			$l =~ s/^(\d+:\d+:\d+)\s(AM|PM)/$1/;

			if ($l =~ m#IFACE\s+#) {
				if ($#headers == -1) {
					push(@headers, split(m#\s+#, $l));
					next;
				} else {
					last;
				}
			}
			# Empty line, maybe the end of a report
			if (($l eq '') && ($#headers >= 0)) {
				last;
			}
			# Get all values reported
			if ($#headers >= 0) {
				my @values = ();
				push(@values, split(m#\s+#, $l));
				last if ($#values != $#headers);
				if (!grep(m#^$values[1]$#, @dev_list)) {
					push(@dev_list, $values[1]);
				}
			}
		}
		close(IN);

	}

	return @dev_list;
}


sub write_database_info
{
	my $db = shift;
	my $src_base = shift;

	return if (($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));

	my $next = $#{$sysinfo{EXTENSION}{$db}} + 1;
	my $extlist = join(',', @{$sysinfo{EXTENSION}{$db}});
	$extlist = ' (' . $extlist . ')' if ($extlist);
	my $nsch = $#{$sysinfo{SCHEMA}{$db}} + 1;
	my $schlist = join(',', @{$sysinfo{SCHEMA}{$db}});
	$schlist = ' (' . $schlist . ')' if ($schlist);
	my $procount = $#{$sysinfo{PROCEDURE}{$db}} + 1;
	my $trigcount = $sysinfo{TRIGGER}{$db} || 0;
	my $last_vacuum = $OVERALL_STATS{$db}{last_vacuum} || '-';
	my $last_analyze = $OVERALL_STATS{$db}{last_analyze} || '-';


	my $objects_count = '';
	foreach my $k (sort keys %RELKIND) {
	        $objects_count .= qq{<li><span class="figure">$OVERALL_STATS{'class'}{$db}{$k}</span> <span class="figure-label">} . lcfirst($RELKIND{$k}) . qq{</span></li>} if (exists $OVERALL_STATS{'class'}{$db}{$k});
	}
	my $dbsize = &pretty_print_size($OVERALL_STATS{'database'}{$db}{'size'});
	print qq{
<ul id="slides">
<li class="slide active-slide" id="database-info-slide">
	<div id="database-info"><br/><br/><br/></div>
	<div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
              <i class="fa fa-desktop fa-2x pull-left fa-border"></i><h2>Database $db</h2>
              </div>
              <div class="panel-body">
		<div class="key-figures">
		<ul>
		<li></li>
	        <li><span class="figure">$dbsize</span> <span class="figure-label">Total size</span></li>
	        <li><span class="figure">$next</span> <span class="figure-label">Installed extensions$extlist</span></li>
	        <li><span class="figure">$nsch</span> <span class="figure-label">Schemas$schlist</span></li>
	        <li><span class="figure">$last_vacuum</span> <span class="figure-label">Last manual vacuum</span></li>
	        <li><span class="figure">$last_analyze</span> <span class="figure-label">Last manual analyze</span></li>
	        <li><span class="figure">$procount</span> <span class="figure-label">Stored procedures</span></li>
	        <li><span class="figure">$trigcount</span> <span class="figure-label">Triggers</span></li>
		$objects_count
		</ul>
		</div>
              </div>
              </div>
            </div><!--/span-->
	</div>
</li>
</ul>
};

}

sub compute_postgresql_stat
{
	my ($in_dir, $file, $src_base, %data_info) = @_;

	print STDERR "DEBUG: reading statistics in file $in_dir/$file\n" if ($DEBUG);

	# Compute graphs following the data file
	my $fctname = $file;
	$fctname =~ s/\.csv(\.gz)?//;
	$fctname =~ s/\.gz//;
	$fctname =~ s/_all_/_user_/;
	$fctname =~ s/\./_/g;
	$fctname->($in_dir, $file, $INTERVAL);
}

sub compute_postgresql_report
{
	my ($file, $src_base, %data_info) = @_;

	# Compute graphs following the data file
	my $fctname = $file;
	$fctname =~ s/\.csv(\.gz)?//;
	$fctname =~ s/\.gz//;
	$fctname =~ s/_all_/_user_/;
	$fctname =~ s/\./_/g;

	print STDERR "DEBUG: creating reports from statistics $fctname.\n" if ($DEBUG);
	$fctname .= '_report';
	$fctname->($INTERVAL, $src_base, $DATABASE, %data_info);
}


# Compute statistics of database statistics
sub pg_stat_database
{
	my ($in_dir, $file) = @_;

	my %start_vals = ();
	my $tmp_val = 0;
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | datid | datname | numbackends | xact_commit | xact_rollback | blks_read | blks_hit | tup_returned | tup_fetched | tup_inserted | tup_updated | tup_deleted | conflicts | stats_reset | temp_files | temp_bytes | deadlocks | blk_read_time | blk_write_time

		push(@global_databases, $data[2]) if (!grep(/^$data[2]$/, @global_databases));
		push(@{$start_vals{$data[2]}}, @data) if ($#{$start_vals{$data[2]}} < 0);

		$OVERALL_STATS{'start_date'} = $data[0] if (!$OVERALL_STATS{'start_date'} || ($OVERALL_STATS{'start_date'} gt $data[0]));
		$OVERALL_STATS{'end_date'} = $data[0] if (!$OVERALL_STATS{'end_date'} || ($OVERALL_STATS{'end_date'} lt $data[0]));

		if ($#data >= 8) {

			(($data[8] - $start_vals{$data[2]}[8]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[8] - $start_vals{$data[2]}[8]);
			if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
				$all_stat_database{$data[0]}{$data[2]}{returned} = $tmp_val;
				$all_stat_database{$data[0]}{all}{returned} += $tmp_val;
			} else {
				$OVERALL_STATS{'cluster'}{returned} += $tmp_val;
				$OVERALL_STATS{'database'}{$data[2]}{returned} += $tmp_val;
			}

			(($data[9] - $start_vals{$data[2]}[9]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[9] - $start_vals{$data[2]}[9]);
			if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
				$all_stat_database{$data[0]}{$data[2]}{fetched} = $tmp_val;
				$all_stat_database{$data[0]}{all}{fetched} += $tmp_val;
			} else {
				$OVERALL_STATS{'cluster'}{fetched} += $tmp_val;
				$OVERALL_STATS{'database'}{$data[2]}{fetched} += $tmp_val;
			}

			# Gather insert statement
			(($data[10] - $start_vals{$data[2]}[10]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[10] - $start_vals{$data[2]}[10]);
			if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
				$all_stat_database{$data[0]}{$data[2]}{insert} = $tmp_val;
				$all_stat_database{$data[0]}{all}{insert} += $tmp_val;
			} else {
				$OVERALL_STATS{'cluster'}{insert} += $tmp_val;
				$OVERALL_STATS{'database'}{$data[2]}{insert} += $tmp_val;
			}

			# Gather update statement
			(($data[11] - $start_vals{$data[2]}[11]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[11] - $start_vals{$data[2]}[11]);
			if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
				$all_stat_database{$data[0]}{$data[2]}{update} = $tmp_val;
				$all_stat_database{$data[0]}{all}{update} += $tmp_val;
			} else {
				$OVERALL_STATS{'cluster'}{update} += $tmp_val;
				$OVERALL_STATS{'database'}{$data[2]}{update} += $tmp_val;
			}

			# Gather delete statement
			(($data[12] - $start_vals{$data[2]}[12]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[12] - $start_vals{$data[2]}[12]);
			if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
				$all_stat_database{$data[0]}{$data[2]}{delete} = $tmp_val;
				$all_stat_database{$data[0]}{all}{delete} += $tmp_val;
			} else {
				$OVERALL_STATS{'cluster'}{delete} += $tmp_val;
				$OVERALL_STATS{'database'}{$data[2]}{delete} += $tmp_val;
			}

		}

		# Gather blks_read
		(($data[6] - $start_vals{$data[2]}[6]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[6] - $start_vals{$data[2]}[6]);
		if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
			$all_stat_database{$data[0]}{$data[2]}{blks_read} = $tmp_val;
			$all_stat_database{$data[0]}{all}{blks_read} += $tmp_val;
		} else {
			$OVERALL_STATS{'cluster'}{blks_read} += $tmp_val;
			$OVERALL_STATS{'database'}{$data[2]}{blks_read} += $tmp_val;
		}

		# Gather blks_hit
		(($data[7] - $start_vals{$data[2]}[7]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[7] - $start_vals{$data[2]}[7]);
		if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
			$all_stat_database{$data[0]}{$data[2]}{blks_hit} = $tmp_val;
			$all_stat_database{$data[0]}{all}{blks_hit} += $tmp_val;
		} else {
			$OVERALL_STATS{'cluster'}{blks_hit} += $tmp_val;
			$OVERALL_STATS{'database'}{$data[2]}{blks_hit} += $tmp_val;
		}

		# Gather number of running backend
		if ($data[3]) {
			$all_stat_database{$data[0]}{$data[2]}{nbackend} = $data[3];
			$all_stat_database{$data[0]}{all}{nbackend} += $data[3];
		} else {
			$OVERALL_STATS{'cluster'}{nbackend} += $tmp_val;
			$OVERALL_STATS{'database'}{$data[2]}{nbackend} += $tmp_val;
		}

		# Gather number of committed transaction
		(($data[4] - $start_vals{$data[2]}[4]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[4] - $start_vals{$data[2]}[4]);
		if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
			$all_stat_database{$data[0]}{$data[2]}{xact_commit} = $tmp_val;
			$all_stat_database{$data[0]}{all}{xact_commit} += $tmp_val;
		} else {
			$OVERALL_STATS{'cluster'}{xact_commit} += $tmp_val;
			$OVERALL_STATS{'database'}{$data[2]}{xact_commit} += $tmp_val;
		}

		# Gather number of rollbacked transaction
		(($data[5] - $start_vals{$data[2]}[5]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[5] - $start_vals{$data[2]}[5]);
		if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
			$all_stat_database{$data[0]}{$data[2]}{xact_rollback} = $tmp_val;
			$all_stat_database{$data[0]}{all}{xact_rollback} += $tmp_val;
		} else {
			$OVERALL_STATS{'cluster'}{xact_rollback} += $tmp_val;
			$OVERALL_STATS{'database'}{$data[2]}{xact_rollback} += $tmp_val;
		}

		# Gather number of canceled queries
		if ($#data >= 13) {
			(($data[13] - $start_vals{$data[2]}[13]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[13] - $start_vals{$data[2]}[13]);
			if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
				$all_stat_database{$data[0]}{$data[2]}{canceled_queries} = $tmp_val;
				$all_stat_database{$data[0]}{all}{canceled_queries} += $tmp_val;
			} else {
				$OVERALL_STATS{'cluster'}{canceled_queries} += $tmp_val;
				$OVERALL_STATS{'database'}{$data[2]}{canceled_queries} += $tmp_val;
			}
		}

		# Gather number of temporary data and deadlock
		if ($#data > 15) {
			(($data[15] - $start_vals{$data[2]}[15]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[15] - $start_vals{$data[2]}[15]);
			if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
				$all_stat_database{$data[0]}{$data[2]}{temp_files} = $tmp_val;
				$all_stat_database{$data[0]}{all}{temp_files} += $tmp_val;
			} else {
				$OVERALL_STATS{'cluster'}{temp_files} += $tmp_val;
				$OVERALL_STATS{'database'}{$data[2]}{temp_files} += $tmp_val;
			}

			(($data[16] - $start_vals{$data[2]}[16]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[16] - $start_vals{$data[2]}[16]);
			if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
				$all_stat_database{$data[0]}{$data[2]}{temp_bytes} = $tmp_val;
				$all_stat_database{$data[0]}{all}{temp_bytes} += $tmp_val;
			} else {
				$OVERALL_STATS{'cluster'}{temp_bytes} += $tmp_val;
				$OVERALL_STATS{'database'}{$data[2]}{temp_bytes} += $tmp_val;
			}

			(($data[17] - $start_vals{$data[2]}[17]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[17] - $start_vals{$data[2]}[17]);
			if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
				$all_stat_database{$data[0]}{$data[2]}{deadlocks} = $tmp_val;
				$all_stat_database{$data[0]}{all}{deadlocks} += $tmp_val;
			} else {
				$OVERALL_STATS{'cluster'}{deadlocks} += $tmp_val;
				$OVERALL_STATS{'database'}{$data[2]}{deadlocks} += $tmp_val;
			}
		}

		@{$start_vals{$data[2]}} = ();
		push(@{$start_vals{$data[2]}}, @data);
	}
	$curfh->close();
	push(@global_databases, 'all') if (($#global_databases >= 0) && !grep(/^all$/, @global_databases));

}

# Compute graphs of database statistics
sub pg_stat_database_report
{
	my ($interval, $src_base, $db_glob, %data_info) = @_;

	my %database_stat = ();
	my %total_query_type = ();
	my %has_conn = ();
	my $has_tuples = 0;
	my $has_temp = 0;
	my $has_conflict = 0;
	foreach my $time (sort {$a <=> $b} keys %all_stat_database) {
		foreach my $db (@global_databases) {
			next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));

			foreach my $k (qw(insert returned fetched update delete blks_read blks_hit nbackend xact_commit xact_rollback canceled_queries deadlocks temp_files temp_bytes)) {
				$all_stat_database{$time}{$db}{$k} ||= 0;

			}

			# It depends on the postgresql version
			if (!$has_tuples) {
				foreach my $k (keys %{$all_stat_database{$time}{$db}}) {
					if (grep(/^$k$/, 'insert','returned','fetched','update','delete')) {
						$has_tuples = 1;
						last;
					}
				}
			}
			if ($has_tuples) {
				$database_stat{$db}{insert} .= '[' . $time . ',' . sprintf("%0.2f", ($all_stat_database{$time}{$db}{insert}/$interval)) . '],';
				$database_stat{$db}{returned} .= '[' . $time . ',' . sprintf("%0.2f", ($all_stat_database{$time}{$db}{returned}/$interval)) . '],';
				$database_stat{$db}{fetched} .= '[' . $time . ',' . sprintf("%0.2f", ($all_stat_database{$time}{$db}{fetched}/$interval)) . '],';
				$database_stat{$db}{update} .= '[' . $time . ',' . sprintf("%0.2f", ($all_stat_database{$time}{$db}{update}/$interval)) . '],';
				$database_stat{$db}{delete} .= '[' . $time . ',' . sprintf("%0.2f", ($all_stat_database{$time}{$db}{delete}/$interval)) . '],';
				$total_query_type{$db}{'all'} +=  $all_stat_database{$time}{$db}{insert} + $all_stat_database{$time}{$db}{returned} + $all_stat_database{$time}{$db}{update} + $all_stat_database{$time}{$db}{delete};

				$total_query_type{$db}{'insert'} += $all_stat_database{$time}{$db}{insert};
				$total_query_type{$db}{'delete'} += $all_stat_database{$time}{$db}{delete};
				$total_query_type{$db}{'update'} += $all_stat_database{$time}{$db}{update};
				$total_query_type{$db}{'select'} += $all_stat_database{$time}{$db}{returned};
			}
			$all_stat_database{$time}{$db}{blks_read} ||= 0;
			$all_stat_database{$time}{$db}{blks_hit} ||= 0;
			$database_stat{$db}{blks_read} .= '[' . $time . ',' . sprintf("%0.2f", ($all_stat_database{$time}{$db}{blks_read}/$interval)) . '],';
			$database_stat{$db}{blks_hit} .= '[' . $time . ',' . sprintf("%0.2f", ($all_stat_database{$time}{$db}{blks_hit}/$interval)) . '],';

			if (($all_stat_database{$time}{$db}{blks_read} + $all_stat_database{$time}{$db}{blks_hit}) > 0) {
				$database_stat{$db}{ratio_hit_miss} .= '[' . $time . ',' . sprintf("%0.2f", ($all_stat_database{$time}{$db}{blks_hit}*100)/($all_stat_database{$time}{$db}{blks_read} + $all_stat_database{$time}{$db}{blks_hit})) . '],';
			} else {
				$database_stat{$db}{ratio_hit_miss} .= '[' . $time . ',0],';
			}
			$database_stat{$db}{nbackend} .= '[' . $time . ',' . ($all_stat_database{$time}{$db}{nbackend}||0) . '],';
			$has_conn{$db} = 1 if ($all_stat_database{$time}{$db}{nbackend});
			$database_stat{$db}{xact_commit} .= '[' . $time . ',' . sprintf("%0.2f", ($all_stat_database{$time}{$db}{xact_commit}||0)/$interval) . '],';
			$database_stat{$db}{xact_rollback} .= '[' . $time . ',' . sprintf("%0.2f", ($all_stat_database{$time}{$db}{xact_rollback}||0)/$interval) . '],';
			# It depends on the postgresql version
			if (!$has_conflict) {
				foreach my $k (keys %{$all_stat_database{$time}{$db}}) {
					if ($k eq 'canceled_queries') {
						$has_conflict = 1;
						last;
					}
				}
			}
			if ($has_conflict) {
				$database_stat{$db}{canceled_queries} .= '[' . $time . ',' . ($all_stat_database{$time}{$db}{canceled_queries}||0) . '],';
			}
			# It depends on the postgresql version
			if (!$has_temp) {
				foreach my $k (keys %{$all_stat_database{$time}{$db}}) {
					if (grep(/^$k$/, 'deadlocks','temp_files','temp_bytes')) {
						$has_temp = 1;
						last;
					}
				}
			}
			if ($has_temp) {
				$database_stat{$db}{deadlocks} .= '[' . $time . ',' . ($all_stat_database{$time}{$db}{deadlocks}||0) . '],';
				$database_stat{$db}{temp_files} .= '[' . $time . ',' . ($all_stat_database{$time}{$db}{temp_files}||0) . '],';
				$database_stat{$db}{temp_bytes} .= '[' . $time . ',' . sprintf("%0.2f", ($all_stat_database{$time}{$db}{temp_bytes}||0)/$interval) . '],';
			}
		}
	}
	%all_stat_database = ();

	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		foreach my $db (sort keys %database_stat) {
			next if ($DATABASE && ($db ne $DATABASE));
			next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
			next if ($data_info{$id}{name} ne $REAL_ACTION);
			if ($data_info{$id}{name} eq 'database-write_ratio') {

				if ($has_tuples) {
					$database_stat{$db}{insert} =~ s/,$//;
					$database_stat{$db}{update} =~ s/,$//;
					$database_stat{$db}{delete} =~ s/,$//;
				}
				if ($db ne 'all') {
					print &flotr2_linegraph_array($IDX++, 'database-write_ratio', \%{$data_info{$id}}, $db, $database_stat{$db}{insert}, $database_stat{$db}{update}, $database_stat{$db}{delete});
				} else {
					print &flotr2_linegraph_array($IDX++, 'cluster-write_ratio', \%{$data_info{$id}}, $db, $database_stat{$db}{insert}, $database_stat{$db}{update}, $database_stat{$db}{delete});
				}

			} elsif ($data_info{$id}{name} eq 'database-read_ratio') {

				if ($has_tuples) {
					$database_stat{$db}{returned} =~ s/,$//;
					$database_stat{$db}{fetched} =~ s/,$//;
				}
				if ($db ne 'all') {
					print &flotr2_linegraph_array($IDX++, 'database-read_ratio', \%{$data_info{$id}}, $db, $database_stat{$db}{returned}, $database_stat{$db}{fetched});
				} else {
					print &flotr2_linegraph_array($IDX++, 'cluster-read_ratio', \%{$data_info{$id}}, $db, $database_stat{$db}{returned}, $database_stat{$db}{fetched});
				}

			} elsif ($data_info{$id}{name} eq 'database-read_write_query') {
				if (exists $total_query_type{$db}{'all'} && ($total_query_type{$db}{'all'} > 0)) {
					my %data = ();
					foreach my $t (keys %{$total_query_type{$db}}) {
						next if ($t eq 'all');
						$data{$t} = sprintf("%0.2f", $total_query_type{$db}{$t}*100/$total_query_type{$db}{'all'});
					}
					if ($db ne 'all') {
						print &flotr2_piegraph($IDX++, 'database-read_write_query', \%{$data_info{$id}}, $db, %data);
					} else {
						print &flotr2_piegraph($IDX++, 'cluster-read_write_query', \%{$data_info{$id}}, $db, %data);
					}
				}

			} elsif ($data_info{$id}{name} eq 'database-cache_ratio') {

				$database_stat{$db}{blks_read} =~ s/,$//;
				$database_stat{$db}{blks_hit} =~ s/,$//;
				if ($db ne 'all') {
					print &flotr2_linegraph_array($IDX++, 'database-cache_ratio', \%{$data_info{$id}}, $db, $database_stat{$db}{blks_hit}, $database_stat{$db}{blks_read}, $database_stat{$db}{ratio_hit_miss});
				} else {
					print &flotr2_linegraph_array($IDX++, 'cluster-cache_ratio', \%{$data_info{$id}}, $db, $database_stat{$db}{blks_hit}, $database_stat{$db}{blks_read}, $database_stat{$db}{ratio_hit_miss});
				}
				delete $database_stat{$db}{blks_hit};
				delete $database_stat{$db}{blks_read};
				delete $database_stat{$db}{ratio_hit_miss};

			} elsif ($data_info{$id}{name} eq 'database-commits_rollbacks') {

				$database_stat{$db}{xact_commit} =~ s/,$//;
				$database_stat{$db}{xact_rollback} =~ s/,$//;
				$database_stat{$db}{nbackend} =~ s/,$//;
				if ($db ne 'all') {
					print &flotr2_linegraph_array($IDX++, 'database-commits_rollbacks', \%{$data_info{$id}}, $db, $database_stat{$db}{xact_commit}, $database_stat{$db}{xact_rollback}, $database_stat{$db}{nbackend});
				} else {
					print &flotr2_linegraph_array($IDX++, 'cluster-commits_rollbacks', \%{$data_info{$id}}, $db, $database_stat{$db}{xact_commit}, $database_stat{$db}{xact_rollback}, $database_stat{$db}{nbackend});
				}
				delete $database_stat{$db}{xact_commit};
				delete $database_stat{$db}{xact_rollback};
			}
		}
	}
	
	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		my %data = ();
		my $found = 0;
		foreach my $db (sort keys %database_stat) {
			next if ($DATABASE && ($DATABASE ne 'all') && ($db ne $DATABASE));
			next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));

			if ($data_info{$id}{name} eq 'database-backends') {
				$database_stat{$db}{nbackend} =~ s/,$//;
				$data{$db} = $database_stat{$db}{nbackend};
				if (($db ne 'all') && ($DATABASE ne 'all')) {
					print &flotr2_linegraph_array($IDX++, $data_info{$id}{name}, \%{$data_info{$id}}, $db, $database_stat{$db}{nbackend});
				}
				delete $database_stat{$db}{nbackend};

			} elsif ($has_conflict && ($data_info{$id}{name} eq 'database-canceled_queries')) {

				$database_stat{$db}{canceled_queries} =~ s/,$//;
				$data{$db} = $database_stat{$db}{canceled_queries};
				if (($db ne 'all') && ($DATABASE ne 'all')) {
					print &flotr2_linegraph_array($IDX++, $data_info{$id}{name}, \%{$data_info{$id}}, $db, $database_stat{$db}{canceled_queries});
				}
				delete $database_stat{$db}{canceled_queries};

			} elsif ($has_temp && ($data_info{$id}{name} eq 'database-deadlocks')) {
				$database_stat{$db}{deadlocks} =~ s/,$//;
				$data{$db} = $database_stat{$db}{deadlocks};
				if (($db ne 'all') && ($DATABASE ne 'all')) {
					print &flotr2_linegraph_array($IDX++, $data_info{$id}{name}, \%{$data_info{$id}}, $db, $database_stat{$db}{deadlocks});
				}
				delete $database_stat{$db}{deadlocks};

			} elsif ($has_temp && ($data_info{$id}{name} eq 'database-temporary_files')) {

				$database_stat{$db}{temp_files} =~ s/,$//;
				$data{$db} = $database_stat{$db}{temp_files};
				if (($db ne 'all') && ($DATABASE ne 'all')) {
					print &flotr2_linegraph_array($IDX++, $data_info{$id}{name}, \%{$data_info{$id}}, $db, $database_stat{$db}{temp_files});
				}
				delete $database_stat{$db}{temp_files};

			} elsif ($has_temp && ($data_info{$id}{name} eq 'database-temporary_bytes')) {

				$database_stat{$db}{temp_bytes} =~ s/,$//;
				$data{$db} = $database_stat{$db}{temp_bytes};
				if (($db ne 'all') && ($DATABASE ne 'all')) {
					print &flotr2_linegraph_array($IDX++, $data_info{$id}{name}, \%{$data_info{$id}}, $db, $database_stat{$db}{temp_bytes});
				}
				delete $database_stat{$db}{temp_bytes};

			}
		}
		if ($db_glob eq 'all') {
			my $name = $data_info{$id}{name};
			$name =~ s/^database/cluster/;
			if ($has_temp && ($data_info{$id}{name} eq 'database-temporary_files')) {
				print &flotr2_linegraph_hash($IDX++, $name, \%{$data_info{$id}}, 'all', %data);
			}
			if ($has_temp && ($data_info{$id}{name} eq 'database-temporary_bytes')) {
				print &flotr2_linegraph_hash($IDX++, $name, \%{$data_info{$id}}, 'all', %data);
			}
			if ($data_info{$id}{name} eq 'database-backends') {
				print &flotr2_linegraph_hash($IDX++, $name, \%{$data_info{$id}}, 'all', %data);
			}
			if ($has_temp && ($data_info{$id}{name} eq 'database-deadlocks')) {
				print &flotr2_linegraph_hash($IDX++, $name, \%{$data_info{$id}}, 'all', %data);
			}
			if ($has_conflict && ($data_info{$id}{name} eq 'database-canceled_queries')) {
				print &flotr2_linegraph_hash($IDX++, $name, \%{$data_info{$id}}, 'all', %data);
			}
		}
	}
}

# Compute statistics of database conflict statistics
sub pg_stat_database_conflicts
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %start_vals = ();
	my $tmp_val = 0;
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));
		# timestamp | datid | datname | confl_tablespace | confl_lock | confl_snapshot | confl_bufferpin | confl_deadlock

		# Get database size statistics
		push(@{$start_vals{$data[2]}}, @data) if ($#{$start_vals{$data[2]}} < 0);

		(($data[3] - $start_vals{$data[2]}[3]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[3] - $start_vals{$data[2]}[3]);
		$all_stat_database_conflicts{$data[2]}{tablespace} += $tmp_val;
		$all_stat_database_conflicts{'all'}{tablespace} += $tmp_val;

		(($data[4] - $start_vals{$data[2]}[4]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[4] - $start_vals{$data[2]}[4]);
		$all_stat_database_conflicts{$data[2]}{lock} += $tmp_val;
		$all_stat_database_conflicts{'all'}{lock} += $tmp_val;

		(($data[5] - $start_vals{$data[2]}[5]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[5] - $start_vals{$data[2]}[5]);
		$all_stat_database_conflicts{$data[2]}{snapshot} += $tmp_val;
		$all_stat_database_conflicts{'all'}{snapshot} += $tmp_val;

		(($data[6] - $start_vals{$data[2]}[6]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[6] - $start_vals{$data[2]}[6]);
		$all_stat_database_conflicts{$data[2]}{bufferpin} += $tmp_val;
		$all_stat_database_conflicts{'all'}{bufferpin} += $tmp_val;

		(($data[7] - $start_vals{$data[2]}[7]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[7] - $start_vals{$data[2]}[7]);
		$all_stat_database_conflicts{$data[2]}{deadlock} += $tmp_val;
		$all_stat_database_conflicts{'all'}{deadlock} += $tmp_val;

		@{$start_vals{$data[2]}} = ();
		push(@{$start_vals{$data[2]}}, @data);

	}
	$curfh->close();
}

# Compute graphs of database conflict statistics
sub pg_stat_database_conflicts_report
{
	my ($interval, $src_base, $db_glob, %data_info) = @_;

	my %database_stat = ();
	my %total_count = ();
	my $id = &get_data_id('database-conflicts', %data_info);
	foreach my $db (sort keys %all_stat_database_conflicts) {

		next if ($DATABASE && ($DATABASE ne 'all') && ($db ne $DATABASE));
		next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
		my $total = 0;
		foreach my $k (sort keys %{$all_stat_database_conflicts{$db}}) {
			$total += $all_stat_database_conflicts{$db}{$k};
		}
		#next if (!$total);
		my %conflict_type = ();
		if ($conflict_type{tablespace} || $conflict_type{lock} || $conflict_type{snapshot} || $conflict_type{bufferpin} || $conflict_type{deadlock}) {
			$conflict_type{tablespace} = sprintf("%0.2f", ($all_stat_database_conflicts{$db}{'tablespace'}*100)/$total);
			$conflict_type{lock} = sprintf("%0.2f", ($all_stat_database_conflicts{$db}{'lock'}*100)/$total);
			$conflict_type{snapshot} = sprintf("%0.2f", ($all_stat_database_conflicts{$db}{'snapshot'}*100)/$total);
			$conflict_type{bufferpin} =  sprintf("%0.2f", ($all_stat_database_conflicts{$db}{'bufferpin'}*100)/$total);
			$conflict_type{deadlock} =  sprintf("%0.2f", ($all_stat_database_conflicts{$db}{'deadlock'}*100)/$total);
		}
		if (($db ne 'all') && ($DATABASE ne 'all') && ($ACTION !~ /^cluster/)) {
			print &flotr2_piegraph($IDX++, 'database-conflicts', \%{$data_info{$id}}, $db, %conflict_type);
		} elsif (($db eq 'all') && ($DATABASE eq 'all')) {
			print &flotr2_piegraph($IDX++, 'cluster-conflicts', \%{$data_info{$id}}, $db, %conflict_type);
		}
	}
	%all_stat_database_conflicts = ();
}

# Compute statistics of database size statistics
sub pg_database_size
{
	my ($in_dir, $file) = @_;

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		# date_trunc | datid | datname | size
		my @data = split(/;/);
		next if (!&normalize_line(\@data));
		push(@global_databases, $data[2]) if (!grep(/^$data[2]$/, @global_databases));
		# Get database size statistics
		if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
			$all_database_size{$data[0]}{$data[2]} = $data[3];
			$all_database_size{$data[0]}{'all'} += $data[3];
		} else {
			$OVERALL_STATS{'database'}{$data[2]}{'size'} = $data[3];
			$OVERALL_STATS{'start_date'} = $data[0] if (!$OVERALL_STATS{'start_date'} || ($OVERALL_STATS{'start_date'} gt $data[0]));
			$OVERALL_STATS{'end_date'} = $data[0] if (!$OVERALL_STATS{'end_date'} || ($OVERALL_STATS{'end_date'} lt $data[0]));
		}
	}
	$curfh->close();
	push(@global_databases, 'all') if (($#global_databases >= 0) && !grep(/^all$/, @global_databases));
}

# Compute graphs of database size statistics
sub pg_database_size_report
{
	my ($interval, $src_base, $db_glob, %data_info) = @_;

	my %database_stat = ();
	my $total_val = 0;
	foreach my $t (sort {$a <=> $b} keys %all_database_size) {
		foreach my $db (@global_databases) {
			next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
			$database_stat{$db}{size} .= '[' . $t . ',' . ($all_database_size{$t}{$db} || 0) . '],';
		}
	}
	%all_database_size = ();

	my $id = &get_data_id('database-size', %data_info);

	my %data = ();
	foreach my $db (sort keys %database_stat) {
		next if ($DATABASE && ($DATABASE ne 'all') && ($db ne $DATABASE));
		next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
		$database_stat{$db}{size} =~ s/,$//;
		$data{$db} = $database_stat{$db}{size};
		if (($db ne 'all') && ($DATABASE ne 'all') && ($ACTION !~ /^cluster/)) {
			print &flotr2_linegraph_array($IDX++, 'database-size', \%{$data_info{$id}}, $db, $database_stat{$db}{size});
		}
		delete $database_stat{$db}{size};
	}

	if ($ACTION eq 'cluster-size') {
		print &flotr2_linegraph_hash($IDX++, 'cluster-size', \%{$data_info{$id}}, 'all', %data);
	}

}

# Compute statistics of tablespace size
sub pg_tablespace_size
{
	my ($in_dir, $file) = @_;

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	my $total_val = 0;
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | tbspname | size | path

		push(@global_tbspnames, $data[1]) if (!grep(/^$data[1]$/, @global_tbspnames));

		# Get tablespace size statistics
		if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
			$all_tablespace_size{$data[0]}{$data[1]}{size} = $data[2];
			$all_tablespace_size{$data[0]}{$data[1]}{location} = $data[3];
			$all_tablespace_size{$data[0]}{'all'}{size} += $data[2];
		} else {
			$OVERALL_STATS{'tablespace'}{$data[1]}{'size'} = $data[2];
			$OVERALL_STATS{'tablespace'}{$data[1]}{'location'} = $data[3];
		}
	}
	$curfh->close();
	push(@global_tbspnames, 'all') if ($#global_tbspnames > 0);

}

# Compute graphs of tablespace size
sub pg_tablespace_size_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	my $id = &get_data_id('tablespace-size', %data_info);
	my %data = ();
	my $print_after = '';
	my %tablespace_stat = ();
	foreach my $t (sort {$a <=> $b} keys %all_tablespace_size) {
		foreach my $tbsp (@global_tbspnames) {
			$tablespace_stat{$tbsp}{size} .= '[' . $t . ',' . ($all_tablespace_size{$t}{$tbsp}{size}||0) . '],';
			$tablespace_stat{$tbsp}{location} = $all_tablespace_size{$t}{$tbsp}{location} || '';
		}
	}
	foreach my $tbsp (sort keys %tablespace_stat) {
		$tablespace_stat{$tbsp}{size} =~ s/,$//;
		$data{$tbsp} = $tablespace_stat{$tbsp}{size};
		if ($tbsp ne 'all') {
			my $location = "$tbsp";
			$location .= " ($tablespace_stat{$tbsp}{location})" if ($tablespace_stat{$tbsp}{location});
			$print_after .= &flotr2_linegraph_array($IDX++, 'tablespace-size+', \%{$data_info{$id}}, $location, $tablespace_stat{$tbsp}{size});
		}
	}
	%all_tablespace_size = ();

	print &flotr2_linegraph_hash($IDX++, 'tablespace-size', \%{$data_info{$id}}, 'all', %data);
	print $print_after;
}

# Compute statistics about table accesses and vacuum
sub pg_stat_user_tables
{
	my ($in_dir, $file) = @_;

	my %start_vals = ();
	my $tmp_val = 0;
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | dbname | relid | schemaname | relname | seq_scan | seq_tup_read | idx_scan | idx_tup_fetch | n_tup_ins | n_tup_upd | n_tup_del | n_tup_hot_upd | n_live_tup | n_dead_tup | last_vacuum | last_autovacuum | last_analyze | last_autoanalyze | vacuum_count | autovacuum_count | analyze_count | autoanalyze_count

		if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') ) {
			$OVERALL_STATS{$data[1]}{last_vacuum} = $data[15] if (!$OVERALL_STATS{$data[1]}{last_vacuum} || ($data[15] gt $OVERALL_STATS{$data[1]}{last_vacuum}));
			$OVERALL_STATS{$data[1]}{last_autovacuum} = $data[16] if (!$OVERALL_STATS{$data[1]}{last_autovacuum} || ($data[16] gt $OVERALL_STATS{$data[1]}{last_autovacuum}));
			$OVERALL_STATS{$data[1]}{last_analyze} = $data[17] if (!$OVERALL_STATS{$data[1]}{last_analyze} || ($data[17] gt $OVERALL_STATS{$data[1]}{last_analyze}));
			$OVERALL_STATS{$data[1]}{last_autoanalyze} = $data[18] if (!$OVERALL_STATS{$data[1]}{last_autoanalyze} || ($data[18] gt $OVERALL_STATS{$data[1]}{last_autoanalyze}));
		} else {

			next if (($#INCLUDE_DB >= 0) && (!grep($data[1] =~ /^$_$/, @INCLUDE_DB)));

			$data[4] = "$data[3].$data[4]";
			push(@{$start_vals{$data[1]}{$data[4]}}, @data) if ($#{$start_vals{$data[1]}{$data[4]}} < 0);

			# Stores last manual vacuum/analyze
			$all_stat_user_tables{$data[1]}{$data[4]}{last_vacuum} = $data[15] if ($data[15]);
			$all_stat_user_tables{$data[1]}{$data[4]}{last_autovacuum} = $data[16] if ($data[16]);
			$all_stat_user_tables{$data[1]}{$data[4]}{last_analyze} = $data[17] if ($data[17]);
			$all_stat_user_tables{$data[1]}{$data[4]}{last_autoanalyze} = $data[18] if ($data[18]);

			# Get database statistics
			(($data[5] - $start_vals{$data[1]}{$data[4]}[5]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[5] - $start_vals{$data[1]}{$data[4]}[5]);
			$all_vacuum_stat{$data[1]}{$data[4]}{seq_scan} += $tmp_val;
			$all_stat_user_tables{$data[1]}{$data[4]}{seq_scan} = $data[5] || 0;
			(($data[7] - $start_vals{$data[1]}{$data[4]}[7]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[7] - $start_vals{$data[1]}{$data[4]}[7]);
			$all_vacuum_stat{$data[1]}{$data[4]}{idx_scan} += $tmp_val;
			$all_stat_user_tables{$data[1]}{$data[4]}{idx_scan} = $data[6] || 0;
			(($data[9] - $start_vals{$data[1]}{$data[4]}[9]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[9] - $start_vals{$data[1]}{$data[4]}[9]);
			$all_vacuum_stat{$data[1]}{$data[4]}{n_tup_ins} += $tmp_val;
			$all_stat_user_tables{$data[1]}{$data[4]}{n_tup_ins} = $data[9] || 0;
			(($data[10] - $start_vals{$data[1]}{$data[4]}[10]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[10] - $start_vals{$data[1]}{$data[4]}[10]);
			$all_vacuum_stat{$data[1]}{$data[4]}{n_tup_upd} += $tmp_val;
			$all_stat_user_tables{$data[1]}{$data[4]}{n_tup_upd} = $data[10] || 0;
			(($data[11] - $start_vals{$data[1]}{$data[4]}[11]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[11] - $start_vals{$data[1]}{$data[4]}[11]);
			$all_vacuum_stat{$data[1]}{$data[4]}{n_tup_del} += $tmp_val;
			$all_stat_user_tables{$data[1]}{$data[4]}{n_tup_del} = $data[11] || 0;
			(($data[12] - $start_vals{$data[1]}{$data[4]}[12]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[12] - $start_vals{$data[1]}{$data[4]}[12]);
			$all_vacuum_stat{$data[1]}{$data[4]}{n_tup_hot_upd} += $tmp_val;
			$all_stat_user_tables{$data[1]}{$data[4]}{n_tup_hot_upd} = $data[12] || 0;
			$all_stat_user_tables{$data[1]}{$data[4]}{n_dead_tup} = $data[14];
			$all_stat_user_tables{$data[1]}{$data[4]}{n_live_tup} = $data[13];
			$all_stat_user_tables{$data[1]}{$data[4]}{dead_vs_live} = sprintf("%.2f", ($data[14]*100)/(($data[13]+$data[14])||1));
			if ($#data > 19) {
				(($data[19] - $start_vals{$data[1]}{$data[4]}[19]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[19] - $start_vals{$data[1]}{$data[4]}[19]);
				$all_vacuum_stat{$data[1]}{$data[4]}{vacuum_count} += $tmp_val;
				$all_stat_user_tables{$data[1]}{$data[4]}{vacuum_count} = $data[19];
				(($data[20] - $start_vals{$data[1]}{$data[4]}[20]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[20] - $start_vals{$data[1]}{$data[4]}[20]);
				$all_vacuum_stat{$data[1]}{$data[4]}{autovacuum_count} += $tmp_val;
				$all_stat_user_tables{$data[1]}{$data[4]}{autovacuum_count} = $data[20];
				(($data[21] - $start_vals{$data[1]}{$data[4]}[21]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[21] - $start_vals{$data[1]}{$data[4]}[21]);
				$all_vacuum_stat{$data[1]}{$data[4]}{analyze_count} += $tmp_val;
				$all_stat_user_tables{$data[1]}{$data[4]}{analyze_count} = $data[21];
				(($data[22] - $start_vals{$data[1]}{$data[4]}[22]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[22] - $start_vals{$data[1]}{$data[4]}[22]);
				$all_vacuum_stat{$data[1]}{$data[4]}{autoanalyze_count} += $tmp_val;
				$all_stat_user_tables{$data[1]}{$data[4]}{autoanalyze_count} = $data[22];
			}
			@{$start_vals{$data[1]}{$data[4]}} = ();
			push(@{$start_vals{$data[1]}{$data[4]}}, @data);
		}
	}
	$curfh->close();
}

# Compute report about table accesses
sub pg_stat_user_tables_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!$db);

	my $do_vacuum = 0;
	foreach my $t (keys %{$all_vacuum_stat{$db}}) {
		foreach my $k (keys %{$all_vacuum_stat{$db}{$t}}) {
			if (($k =~ /vacuum|analyze/) && $all_vacuum_stat{$db}{$t}{$k}) {
				$do_vacuum = 1;
			}
		}
	}

	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		next if ($data_info{$id}{name} !~ /^table-/);
		next if ($data_info{$id}{name} ne $REAL_ACTION);
		my $table_header = '';
		my $colspan = '';
		if ($data_info{$id}{name} eq 'table-indexes') {
			$table_header = qq{
					<th>Schema.Table</th>
					<th>Sequencial scan</th>
					<th>Index scan</th>
					<th>Index vs Sequencial</th>
};
			$colspan = ' colspan="5"';
		} elsif ($data_info{$id}{name} eq 'table-query-tuples') {
			$table_header = qq{
					<th>Schema.Table</th>
					<th>Inserted</th>
					<th>Updated</th>
					<th>Deleted</th>
					<th>Hot Updated</th>
};
			$colspan = ' colspan="6"';
		} elsif ($data_info{$id}{name} eq 'table-kind-tuples') {
			$table_header = qq{
					<th>Schema.Table</th>
					<th>Live tuples</th>
					<th>Dead tuples</th>
					<th>Dead vs Live</th>
};
			$colspan = ' colspan="5"';
		} elsif ( $do_vacuum && ($data_info{$id}{name} eq 'table-vacuums-analyzes') ) {
			$table_header = qq{
					<th>Schema.Table</th>
					<th>Vacuum</th>
					<th>Autovacuum</th>
					<th>Analyze</th>
					<th>Autoanalyze</th>
					<th>Last vacuum</th>
					<th>Last autovacuum</th>
					<th>Last analyze</th>
					<th>Last autoanalyze</th>
};
			$colspan = ' colspan="10"';
		}
		if (scalar keys %{$all_vacuum_stat{$db}} == 0) {
			$table_header = qq{<td><div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div></td>};
		}
		print qq{
<ul id="slides">
<li class="slide active-slide" id="$data_info{$id}{name}-slide">
      <div id="$data_info{$id}{name}"><br/><br/><br/><br/></div>
<div class="row">
    <div class="col-md-12">
      <div class="panel panel-default">
      <div class="panel-heading">
	<h2><i class="icon-time"></i> $data_info{$id}{menu} on $db database tables</h2>
	<p>$data_info{$id}{description}</p>
      </div>
      <div class="panel-body">
	<div class="analysis-item row-fluid" id="$db-$data_info{$id}{name}">
		<div class="span11">
			<table class="table table-striped sortable" id="$db-$data_info{$id}{name}-table">
				<thead>
					<tr>
					$table_header
					</tr>
				</thead>
				<tbody>
};
		foreach my $tb (sort keys %{$all_vacuum_stat{$db}}) {
			next if ($tb eq 'all');
			next if (($#INCLUDE_TB >= 0) && !grep(/^$tb$/, @INCLUDE_TB));
			my $table_data = '';
			if ($data_info{$id}{name} eq 'table-indexes') {
				if (!$all_vacuum_stat{$db}{$tb}{seq_scan} && !$all_vacuum_stat{$db}{$tb}{idx_scan}) {
					next;
					foreach ('idx_scan','seq_scan') {
						$all_stat_user_tables{$db}{$tb}{$_} ||= 0;
					}
					$all_stat_user_tables{$db}{$tb}{idx_scan_vs_seq_scan} = sprintf("%0.2f", ($all_stat_user_tables{$db}{$tb}{idx_scan}*100)/(($all_stat_user_tables{$db}{$tb}{seq_scan}+$all_stat_user_tables{$db}{$tb}{idx_scan})||1));
					$table_data = qq{<tr><th>$tb</th><td>$all_stat_user_tables{$db}{$tb}{seq_scan}</td><td>$all_stat_user_tables{$db}{$tb}{idx_scan}</td><td>$all_stat_user_tables{$db}{$tb}{idx_scan_vs_seq_scan}%</td></tr>};
				} else {
					foreach ('idx_scan','seq_scan') {
						$all_vacuum_stat{$db}{$tb}{$_} ||= 0;
					}
					$all_vacuum_stat{$db}{$tb}{idx_scan_vs_seq_scan} = sprintf("%0.2f", ($all_vacuum_stat{$db}{$tb}{idx_scan}*100)/(($all_vacuum_stat{$db}{$tb}{seq_scan}+$all_vacuum_stat{$db}{$tb}{idx_scan})||1));
					$table_data = qq{<tr><th>$tb</th><td>$all_vacuum_stat{$db}{$tb}{seq_scan}</td><td>$all_vacuum_stat{$db}{$tb}{idx_scan}</td><td>$all_vacuum_stat{$db}{$tb}{idx_scan_vs_seq_scan}%</td></tr>};
				}
			} elsif ($data_info{$id}{name} eq 'table-query-tuples') {
				if (!$all_vacuum_stat{$db}{$tb}{n_tup_ins} && !$all_vacuum_stat{$db}{$tb}{n_tup_upd} && !$all_vacuum_stat{$db}{$tb}{n_tup_del} && !$all_vacuum_stat{$db}{$tb}{n_tup_hot_upd}) {
					next;
					foreach ('n_tup_ins','n_tup_upd','n_tup_del','n_tup_hot_upd') {
						$all_stat_user_tables{$db}{$tb}{$_} ||= 0;
					}
					$table_data = qq{<tr><th>$tb</th><td>$all_stat_user_tables{$db}{$tb}{n_tup_ins}</td><td>$all_stat_user_tables{$db}{$tb}{n_tup_upd}</td><td>$all_stat_user_tables{$db}{$tb}{n_tup_del}</td><td>$all_stat_user_tables{$db}{$tb}{n_tup_hot_upd}</td></tr>};
				} else {
					foreach ('n_tup_ins','n_tup_upd','n_tup_del','n_tup_hot_upd') {
						$all_vacuum_stat{$db}{$tb}{$_} ||= 0;
					}
					$table_data = qq{<tr><th>$tb</th><td>$all_vacuum_stat{$db}{$tb}{n_tup_ins}</td><td>$all_vacuum_stat{$db}{$tb}{n_tup_upd}</td><td>$all_vacuum_stat{$db}{$tb}{n_tup_del}</td><td>$all_vacuum_stat{$db}{$tb}{n_tup_hot_upd}</td></tr>};
				}
			} elsif ($data_info{$id}{name} eq 'table-kind-tuples') {
				if (!$all_stat_user_tables{$db}{$tb}{n_live_tup} && !$all_stat_user_tables{$db}{$tb}{n_dead_tup}) {
					next;
				}
				foreach ('n_live_tup','n_dead_tup','dead_vs_live') {
					$all_stat_user_tables{$db}{$tb}{$_} ||= 0;
				}
				$table_data = qq{<tr><th>$tb</th><td>$all_stat_user_tables{$db}{$tb}{n_live_tup}</td><td>$all_stat_user_tables{$db}{$tb}{n_dead_tup}</td><td>$all_stat_user_tables{$db}{$tb}{dead_vs_live}%</td></tr>};
			} elsif ( $do_vacuum && ($data_info{$id}{name} eq 'table-vacuums-analyzes') ) {
				if (!$all_vacuum_stat{$db}{$tb}{vacuum_count} && !$all_vacuum_stat{$db}{$tb}{autovacuum_count} && !$all_vacuum_stat{$db}{$tb}{analyze_count} && !$all_vacuum_stat{$db}{$tb}{analyze_count}) {
					next;
					foreach ('vacuum_count','autovacuum_count','analyze_count','autoanalyze_count') {
						$all_stat_user_tables{$db}{$tb}{$_} ||= 0;
					}
					$table_data = qq{<tr><th>$tb</th><td>$all_stat_user_tables{$db}{$tb}{vacuum_count}</td><td>$all_stat_user_tables{$db}{$tb}{autovacuum_count}</td><td>$all_stat_user_tables{$db}{$tb}{analyze_count}</td><td>$all_stat_user_tables{$db}{$tb}{autoanalyze_count}</td>};
				} else  {
					foreach ('vacuum_count','autovacuum_count','analyze_count','autoanalyze_count') {
						$all_vacuum_stat{$db}{$tb}{$_} ||= 0;
					}
					$table_data = qq{<tr><th>$tb</th><td>$all_vacuum_stat{$db}{$tb}{vacuum_count}</td><td>$all_vacuum_stat{$db}{$tb}{autovacuum_count}</td><td>$all_vacuum_stat{$db}{$tb}{analyze_count}</td><td>$all_vacuum_stat{$db}{$tb}{autoanalyze_count}</td>};
				}
				foreach ('last_vacuum','last_autovacuum','last_analyze','last_autoanalyze') {
					$all_stat_user_tables{$db}{$tb}{$_} ||= '-';
				}
				$table_data .= qq{<td>$all_stat_user_tables{$db}{$tb}{last_vacuum}</td><td>$all_stat_user_tables{$db}{$tb}{last_autovacuum}</td><td>$all_stat_user_tables{$db}{$tb}{last_analyze}</td><td>$all_stat_user_tables{$db}{$tb}{last_autoanalyze}</td></tr>};
			}
			if ($table_data) {
				print qq{$table_data};
			}
		}
		print qq{
				</tbody>
			</table>
		</div>
	</div>
	</div>
    </div>
</div>
</li>
</ul>
};
	}
	%all_stat_user_tables = ();
}

# Compute statistics about index scan
sub pg_stat_user_indexes
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %start_vals = ();
	my $tmp_val = 0;
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | dbname | relid | indexrelid | schemaname | relname | indexrelname | idx_scan | idx_tup_read | idx_tup_fetch
		next if (($#INCLUDE_DB >= 0) && (!grep($data[1] =~ /^$_$/, @INCLUDE_DB)));

		$data[6] = "$data[4].$data[5].$data[6]";
		push(@{$start_vals{$data[1]}{$data[6]}}, @data) if ($#{$start_vals{$data[1]}{$data[6]}} < 0);

		# Get database statistics
		(($data[7] - $start_vals{$data[1]}{$data[6]}[7]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[7] - $start_vals{$data[1]}{$data[6]}[7]);
		$all_stat_user_indexes{$data[1]}{$data[6]}{idx_scan} += $tmp_val;

		(($data[8] - $start_vals{$data[1]}{$data[6]}[8]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[8] - $start_vals{$data[1]}{$data[6]}[8]);
		$all_stat_user_indexes{$data[1]}{$data[6]}{idx_tup_read} += $tmp_val;

		(($data[9] - $start_vals{$data[1]}{$data[6]}[9]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[9] - $start_vals{$data[1]}{$data[6]}[9]);
		$all_stat_user_indexes{$data[1]}{$data[6]}{idx_tup_fetch} += $tmp_val;

		@{$start_vals{$data[1]}{$data[6]}} = ();
		push(@{$start_vals{$data[1]}{$data[6]}}, @data);
	}
	$curfh->close();
}

# Compute report about index scan
sub pg_stat_user_indexes_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!$db);

	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		next if ($data_info{$id}{name} !~ /^index-/);
		my $table_header = '';
		my $colspan =  ' colspan="4"';
		if ($data_info{$id}{name} eq 'index-scan') {
			$table_header = qq{
					<th>Schema.Table.Index</th>
					<th>Index scan</th>
					<th>Index entries returned</th>
					<th>Live table rows fetched</th>
};
		}
		if (scalar keys %{$all_class_size{$db}} == 0) {
			$table_header = qq{<td><div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div></td>};
		}
		print qq{
<ul id="slides">
<li class="slide active-slide" id="$data_info{$id}{name}-slide">
      <div id="$data_info{$id}{name}"><br/><br/><br/><br/></div>
<div class="row">
    <div class="col-md-12">
      <div class="panel panel-default">
      <div class="panel-heading">
	<h2><i class="icon-time"></i> $data_info{$id}{menu} on $db database indexes</h2>
	<p>$data_info{$id}{description}</p>
      </div>
      <div class="panel-body">
	<div class="analysis-item row-fluid" id="$db-$data_info{$id}{name}">
		<div class="span11">
			<table class="table table-striped sortable" id="$db-$data_info{$id}{name}-table">
				<thead>
					<tr>
						$table_header
					</tr>
				</thead>
				<tbody>
};
		my $found_table_stat = 0;
		foreach my $idx (sort keys %{$all_stat_user_indexes{$db}}) {
			next if ($idx eq 'all');
			next if (($#INCLUDE_TB >= 0) && !grep(/^$idx$/, @INCLUDE_TB));
			my $table_data = '';
			if ($data_info{$id}{name} eq 'index-scan') {
				if (!$all_stat_user_indexes{$db}{$idx}{idx_scan} && !$all_stat_user_indexes{$db}{$idx}{idx_tup_read} && !$all_stat_user_indexes{$db}{$idx}{idx_tup_fetch}) {
					next;
				}
				foreach ('idx_scan','idx_tup_read','idx_tup_fetch') {
					$all_stat_user_indexes{$db}{$idx}{$_} ||= 0;
				}
				$table_data = qq{<tr><th>$idx</th><td>$all_stat_user_indexes{$db}{$idx}{idx_scan}</td><td>$all_stat_user_indexes{$db}{$idx}{idx_tup_read}</td><td>$all_stat_user_indexes{$db}{$idx}{idx_tup_fetch}</td></tr>};
			}
			if ($table_data) {
				print qq{$table_data} if ($table_data);
			}
		}
		print qq{
				</tbody>
			</table>
		</div>
	</div>
	</div>
    </div>
</div>
</li>
</ul>
};
	}
	%all_stat_user_tables = ();
}

# Compute stats for table I/O
sub pg_statio_user_tables
{
	my ($in_dir, $file, $interval) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %start_vals = ();
	my $tmp_val = 0;
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | dbname | relid | schemaname | relname | heap_blks_read | heap_blks_hit | idx_blks_read | idx_blks_hit | toast_blks_read | toast_blks_hit | tidx_blks_read | tidx_blks_hit
		next if (($#INCLUDE_DB >= 0) && (!grep($data[1] =~ /^$_$/, @INCLUDE_DB)));

		$data[4] = "$data[3].$data[4]";

		push(@{$start_vals{$data[1]}{$data[4]}}, @data) if ($#{$start_vals{$data[1]}{$data[4]}} < 0);

		(($data[5] - $start_vals{$data[1]}{$data[4]}[5]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[5] - $start_vals{$data[1]}{$data[4]}[5]);
		$all_statio_user_tables{$data[0]}{$data[1]}{$data[4]}{heap_blks_read} = int($tmp_val/$interval);

		(($data[6] - $start_vals{$data[1]}{$data[4]}[6]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[6] - $start_vals{$data[1]}{$data[4]}[6]);
		$all_statio_user_tables{$data[0]}{$data[1]}{$data[4]}{heap_blks_hit} = int($tmp_val/$interval);

		(($data[7] - $start_vals{$data[1]}{$data[4]}[7]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[7] - $start_vals{$data[1]}{$data[4]}[7]);
		$all_statio_user_tables{$data[0]}{$data[1]}{$data[4]}{idx_blks_read} = int($tmp_val/$interval);

		(($data[8] - $start_vals{$data[1]}{$data[4]}[8]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[8] - $start_vals{$data[1]}{$data[4]}[8]);
		$all_statio_user_tables{$data[0]}{$data[1]}{$data[4]}{idx_blks_hit} = int($tmp_val/$interval);

		(($data[9] - $start_vals{$data[1]}{$data[4]}[9]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[9] - $start_vals{$data[1]}{$data[4]}[9]);
		$all_statio_user_tables{$data[0]}{$data[1]}{$data[4]}{toast_blks_read} = int($tmp_val/$interval);

		(($data[10] - $start_vals{$data[1]}{$data[4]}[10]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[10] - $start_vals{$data[1]}{$data[4]}[10]);
		$all_statio_user_tables{$data[0]}{$data[1]}{$data[4]}{toast_blks_hit} = int($tmp_val/$interval);

		(($data[11] - $start_vals{$data[1]}{$data[4]}[11]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[11] - $start_vals{$data[1]}{$data[4]}[11]);
		$all_statio_user_tables{$data[0]}{$data[1]}{$data[4]}{tidx_blks_read} = int($tmp_val/$interval);

		(($data[12] - $start_vals{$data[1]}{$data[4]}[12]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[12] - $start_vals{$data[1]}{$data[4]}[12]);
		$all_statio_user_tables{$data[0]}{$data[1]}{$data[4]}{tidx_blks_hit} = int($tmp_val/$interval);

		@{$start_vals{$data[1]}{$data[4]}} = ();
		push(@{$start_vals{$data[1]}{$data[4]}}, @data);
	}
	$curfh->close();
}

# Compute report for table I/O
sub pg_statio_user_tables_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!$db);

	my %is_used = ();
	my %is_toast = ();
	my %statio_usertable = ();
	foreach my $t (sort {$a <=> $b} keys %all_statio_user_tables) {
		foreach my $obj (keys %{ $all_statio_user_tables{$t}{$db} }) {
			$statio_usertable{$db}{$obj}{heap_blks_read} .= '[' . $t . ',' . ($all_statio_user_tables{$t}{$db}{$obj}{heap_blks_read}||0) . '],';
			$statio_usertable{$db}{$obj}{heap_blks_hit} .= '[' . $t . ',' . ($all_statio_user_tables{$t}{$db}{$obj}{heap_blks_hit}||0) . '],';
			$statio_usertable{$db}{$obj}{idx_blks_read} .= '[' . $t . ',' . ($all_statio_user_tables{$t}{$db}{$obj}{idx_blks_read}||0) . '],';
			$statio_usertable{$db}{$obj}{idx_blks_hit} .= '[' . $t . ',' . ($all_statio_user_tables{$t}{$db}{$obj}{idx_blks_hit}||0) . '],';
			$statio_usertable{$db}{$obj}{toast_blks_read} .= '[' . $t . ',' . ($all_statio_user_tables{$t}{$db}{$obj}{toast_blks_read}||0) . '],';
			$statio_usertable{$db}{$obj}{toast_blks_hit} .= '[' . $t . ',' . ($all_statio_user_tables{$t}{$db}{$obj}{toast_blks_hit}||0) . '],';
			$statio_usertable{$db}{$obj}{tidx_blks_read} .= '[' . $t . ',' . ($all_statio_user_tables{$t}{$db}{$obj}{tidx_blks_read}||0) . '],';
			$statio_usertable{$db}{$obj}{tidx_blks_hit} .= '[' . $t . ',' . ($all_statio_user_tables{$t}{$db}{$obj}{tidx_blks_hit}||0) . '],';
			$is_used{$db}{$obj}{is_used} += ($all_statio_user_tables{$t}{$db}{$obj}{heap_blks_read}||0)+($all_statio_user_tables{$t}{$db}{$obj}{heap_blks_hit}||0)+($all_statio_user_tables{$t}{$db}{$obj}{idx_blks_read}||0)+($all_statio_user_tables{$t}{$db}{$obj}{idx_blks_hit}||0)+($all_statio_user_tables{$t}{$db}{$obj}{toast_blks_read}||0)+($all_statio_user_tables{$t}{$db}{$obj}{toast_blks_hit}||0)+($all_statio_user_tables{$t}{$db}{$obj}{tidx_blks_read}||0)+($all_statio_user_tables{$t}{$db}{$obj}{tidx_blks_hit}||0);
			if (!$is_toast{$db}{$obj}{is_toast}) {
				$is_toast{$db}{$obj}{is_toast} += ($all_statio_user_tables{$t}{$db}{$obj}{toast_blks_read}||0)+($all_statio_user_tables{$t}{$db}{$obj}{toast_blks_hit}||0)+($all_statio_user_tables{$t}{$db}{$obj}{tidx_blks_read}||0)+($all_statio_user_tables{$t}{$db}{$obj}{tidx_blks_hit}||0);
			}
		}
	}
	%all_statio_user_tables = ();

	my $id = &get_data_id('statio-table', %data_info);
	if (exists $is_used{$db}) {
		my $rank = 1;
		foreach my $tb (sort {$is_used{$db}{$b} <=> $is_used{$db}{$a} } keys %{$is_used{$db}}) {
			next if (($#INCLUDE_TB >= 0) && !grep(/^$tb$/, @INCLUDE_TB));
			last if ($TOP_STAT && ($rank > $TOP_STAT));
			my $graph_data = '';
			foreach ('heap_blks_read','heap_blks_hit','idx_blks_read','idx_blks_hit','toast_blks_read','toast_blks_hit','tidx_blks_read','tidx_blks_hit') {
				$statio_usertable{$db}{$tb}{$_} =~ s/,$//;
			}
			# if this is a toast table override the normal table values for easy use
			if (exists $is_toast{$db}{$tb}) {
				$statio_usertable{$db}{$tb}{heap_blks_read} = $statio_usertable{$db}{$tb}{toast_blks_read};
				$statio_usertable{$db}{$tb}{heap_blks_hit} = $statio_usertable{$db}{$tb}{toast_blks_hit};
				$statio_usertable{$db}{$tb}{idx_blks_read} = $statio_usertable{$db}{$tb}{tidx_blks_read};
				$statio_usertable{$db}{$tb}{idx_blks_hit} = $statio_usertable{$db}{$tb}{tidx_blks_hit};
			}
			print &flotr2_linegraph_array($IDX++, 'statio-table', \%{$data_info{$id}}, $tb, $statio_usertable{$db}{$tb}{heap_blks_read},$statio_usertable{$db}{$tb}{heap_blks_hit},$statio_usertable{$db}{$tb}{idx_blks_read},$statio_usertable{$db}{$tb}{idx_blks_hit});
			delete $statio_usertable{$db}{$tb};
			$rank++;
		}
	} else {
		print &empty_dataset('statio-index', \%{$data_info{$id}}, 'indexes');
	}
}

# Compute stats for relation buffer cache
sub pg_relation_buffercache
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %start_vals = ();
	my $tmp_val = 0;
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# date_trunc | datname | relname | buffers | relpages | buffered | buffers % | relation %

		next if (($#INCLUDE_DB >= 0) && (!grep($data[1] =~ /^$_$/, @INCLUDE_DB)));

		$data[7] = 100 if ($data[7] > 100);
		$all_relation_buffercache{$data[0]}{$data[1]}{$data[2]}{buffers}      = ($data[3] || 0);
		$all_relation_buffercache{$data[0]}{$data[1]}{$data[2]}{pages}        = ($data[4] || 0);
		$all_relation_buffercache{$data[0]}{$data[1]}{$data[2]}{buffered}     = ($data[5] || 0);
		$all_relation_buffercache{$data[0]}{$data[1]}{$data[2]}{'buffers %'}  = ($data[6] || 0);
		$all_relation_buffercache{$data[0]}{$data[1]}{$data[2]}{'relation %'} = ($data[7] || 0);

	}
	$curfh->close();
};

# Compute report for relation buffer cache
sub pg_relation_buffercache_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!$db);

	my %rel_stat = ();
	my %to_show = ();
	my %buffercache_stat = ();

	foreach my $t (sort {$a <=> $b} keys %all_relation_buffercache) {
		foreach my $obj ( keys %{$all_relation_buffercache{$t}{$db}} ) {
			$rel_stat{$db}{$obj}{buffers}      .= '[' . $t . ',' . ($all_relation_buffercache{$t}{$db}{$obj}{buffers} || 0) . '],';
			$buffercache_stat{$db}{$obj}{buffers} = ($all_relation_buffercache{$t}{$db}{$obj}{buffers} || 0);
			$rel_stat{$db}{$obj}{pages}        .= '[' . $t . ',' . ($all_relation_buffercache{$t}{$db}{$obj}{pages} || 0) . '],';
			$buffercache_stat{$db}{$obj}{pages} = ($all_relation_buffercache{$t}{$db}{$obj}{pages} || 0);
			$rel_stat{$db}{$obj}{buffered}     .= '[' . $t . ',' . ($all_relation_buffercache{$t}{$db}{$obj}{buffered} || 0) . '],';
			$buffercache_stat{$db}{$obj}{buffered} = ($all_relation_buffercache{$t}{$db}{$obj}{buffered} || 0);
			$rel_stat{$db}{$obj}{'buffers %'}  .= '[' . $t . ',' . ($all_relation_buffercache{$t}{$db}{$obj}{'buffers %'} || 0) . '],';
			$buffercache_stat{$db}{$obj}{'buffers %'} = ($all_relation_buffercache{$t}{$db}{$obj}{'buffers %'} || 0);
			$rel_stat{$db}{$obj}{'relation %'} .= '[' . $t . ',' . ($all_relation_buffercache{$t}{$db}{$obj}{'relation %'} || 0) . '],';
			$buffercache_stat{$db}{$obj}{'relation %'} = ($all_relation_buffercache{$t}{$db}{$obj}{'relation %'} || 0);
		}
	}
	%all_relation_buffercache = ();

	my $id = &get_data_id($ACTION, %data_info);

	# Get list of object in the shared buffers
	if ($data_info{$id}{name} eq 'buffercache-relation') {
		my $colspan =  ' colspan="6"';
		my $table_header = qq{
				<th>Relation</th>
				<th>Buffers</th>
				<th>Pages</th>
				<th>Buffered</th>
				<th>Buffers %</th>
				<th>Relation %</th>
};
		if (!exists $buffercache_stat{$db} || scalar keys %{$buffercache_stat{$db}} == 0) {
			$table_header = qq{<td><div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div></td>};
		}
		print qq{
<ul id="slides">
<li class="slide active-slide" id="$data_info{$id}{name}-slide">
      <div id="$data_info{$id}{name}"><br/><br/><br/><br/></div>
<div class="row">
    <div class="col-md-12">
      <div class="panel panel-default">
      <div class="panel-heading">
	<h2><i class="icon-time"></i> $data_info{$id}{menu} on $db database</h2>
	<p>$data_info{$id}{description}</p>
      </div>
      <div class="panel-body">
	<div class="analysis-item row-fluid" id="$db-$data_info{$id}{name}">
		<div class="span11">
			<table class="table table-striped sortable" id="$db-$data_info{$id}{name}-table">
				<thead>
					<tr>
						$table_header
					</tr>
				</thead>
				<tbody>
};
		my $found_stat = 0;
		my $rank = 1;
		foreach my $rel (sort {$buffercache_stat{$db}{$b}{buffers} <=> $buffercache_stat{$db}{$a}{buffers}} keys %{$buffercache_stat{$db}}) {
			next if (($#INCLUDE_TB >= 0) && !grep(/^$rel$/, @INCLUDE_TB));
			last if ($TOP_STAT && ($rank > $TOP_STAT));
			my $table_data = '';
			if ($data_info{$id}{name} eq 'buffercache-relation') {
				if (!$buffercache_stat{$db}{$rel}{buffers} && !$buffercache_stat{$db}{$rel}{pages} && !$buffercache_stat{$db}{$rel}{buffered}) {
					next;
				}
				$to_show{$db}{$rel} = $rank;
				$table_data = "<tr><th>$rel</th><td>$buffercache_stat{$db}{$rel}{buffers}</td><td>$buffercache_stat{$db}{$rel}{pages}</td><td>" . &pretty_print_size($buffercache_stat{$db}{$rel}{buffered}) . "</td><td>$buffercache_stat{$db}{$rel}{'buffers %'}</td><td>$buffercache_stat{$db}{$rel}{'relation %'}</td></tr>\n";
			}
			$rank++;
			if ($table_data) {
				print qq{$table_data} if ($table_data);
			}
		}
		print qq{
				</tbody>
			</table>
		</div>
	</div>
	</div>
    </div>
</div>
</li>
</ul>
};
	}

	# Show shared buffers usage per object
	if ($data_info{$id}{name} eq 'statio-buffercache') {
		my $rank = 1;
		foreach my $rel (sort {$buffercache_stat{$db}{$b}{buffers} <=> $buffercache_stat{$db}{$a}{buffers}} keys %{$buffercache_stat{$db}}) {
			next if (($#INCLUDE_TB >= 0) && !grep(/^$rel$/, @INCLUDE_TB));
			last if ($TOP_STAT && ($rank > $TOP_STAT));
			if (!$buffercache_stat{$db}{$rel}{buffers} && !$buffercache_stat{$db}{$rel}{pages} && !$buffercache_stat{$db}{$rel}{buffered}) {
				next;
			}
			$to_show{$db}{$rel} = $rank;
			$rank++;
		}
		if (exists $to_show{$db}) {
			foreach my $rel (sort {$to_show{$db}{$a} <=> $to_show{$db}{$b} } keys %{$to_show{$db}}) {
				my $graph_data = '';
				foreach ('buffers','pages','buffered','buffers %','relation %') {
					$rel_stat{$db}{$rel}{$_} =~ s/,$//;
				}
				print &flotr2_linegraph_array($IDX++, 'statio-buffercache', \%{$data_info{$id}}, $rel, $rel_stat{$db}{$rel}{buffered},$rel_stat{$db}{$rel}{'relation %'});
			}
		} else {
			print &empty_dataset('statio-buffercache', \%{$data_info{$id}}, 'on');
		}
	}

	%buffercache_stat = ();
}

# Compute stats for index I/O
sub pg_statio_user_indexes
{
	my ($in_dir, $file, $interval) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %start_vals = ();
	my $tmp_val = 0;
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | dbname | relid | indexrelid | schemaname | relname | indexrelname | idx_blks_read | idx_blks_hit

		next if (($#INCLUDE_DB >= 0) && (!grep($data[1] =~ /^$_$/, @INCLUDE_DB)));

		$data[6] = "$data[4].$data[5].$data[6]";

		push(@{$start_vals{$data[1]}{$data[6]}}, @data) if ($#{$start_vals{$data[1]}{$data[6]}} < 0);

		(($data[7] - $start_vals{$data[1]}{$data[6]}[7]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[7] - $start_vals{$data[1]}{$data[6]}[7]);
		$all_statio_all_indexes{$data[0]}{$data[1]}{$data[6]}{idx_blks_read} = int($tmp_val/$interval);

		(($data[8] - $start_vals{$data[1]}{$data[6]}[8]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[8] - $start_vals{$data[1]}{$data[6]}[8]);
		$all_statio_all_indexes{$data[0]}{$data[1]}{$data[6]}{idx_blks_hit} = int($tmp_val/$interval);

		@{$start_vals{$data[1]}{$data[6]}} = ();
		push(@{$start_vals{$data[1]}{$data[6]}}, @data);
	}
	$curfh->close();

}

# Compute report for index I/O
sub pg_statio_user_indexes_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!$db);

	my %statio_userindex = ();
	my %is_used = ();
	foreach my $t (sort {$a <=> $b} keys %all_statio_all_indexes) {
		foreach my $obj (keys %{ $all_statio_all_indexes{$t}{$db} }) {
			$statio_userindex{$db}{$obj}{idx_blks_read} .= '[' . $t . ',' . ($all_statio_all_indexes{$t}{$db}{$obj}{idx_blks_read}||0) . '],';
			$statio_userindex{$db}{$obj}{idx_blks_hit} .= '[' . $t . ',' . ($all_statio_all_indexes{$t}{$db}{$obj}{idx_blks_hit}||0) . '],';
			$is_used{$db}{$obj} += ($all_statio_all_indexes{$t}{$db}{$obj}{idx_blks_hit}||0)+($all_statio_all_indexes{$t}{$db}{$obj}{idx_blks_read}||0);
		}
	}
	%all_statio_all_indexes = ();

	my $id = &get_data_id('statio-index', %data_info);

	if (exists $is_used{$db}) {
		my $rank = 1;
		foreach my $tb (sort {$is_used{$db}{$b} <=> $is_used{$db}{$a} } keys %{$is_used{$db}}) {
			next if (($#INCLUDE_TB >= 0) && !grep(/^$tb$/, @INCLUDE_TB));
			last if ($TOP_STAT && ($rank > $TOP_STAT));
			my $graph_data = '';
			foreach ('idx_blks_read','idx_blks_hit') {
				$statio_userindex{$db}{$tb}{$_} =~ s/,$//;
			}
			print &flotr2_linegraph_array($IDX++, 'statio-index', \%{$data_info{$id}}, $tb, $statio_userindex{$db}{$tb}{idx_blks_read},$statio_userindex{$db}{$tb}{idx_blks_hit});
			delete $statio_userindex{$db}{$tb};
			$rank++;
		}
	} else {
		print &empty_dataset('statio-index', \%{$data_info{$id}}, 'indexes');
	}

}

# Compute statistics of xlog cluster
sub pg_xlog_stat
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | total_file | last_wal_name | wal_recycled | wal_written | max_wal

		# case of pgstats file content
		if ($#data == 3) {
			$all_xlog_stat{$data[0]}{total}++;
		} else {
			$all_xlog_stat{$data[0]}{total} = ($data[1] || 0);
			if ($#data == 5) {
				$all_xlog_stat{$data[0]}{recycled} = ($data[3] || 0);
				$all_xlog_stat{$data[0]}{written}  = ($data[4] || 0);
				$all_xlog_stat{$data[0]}{max_wal}  = (POSIX::ceil($data[5]) || 0);
			}
		}
	}
	$curfh->close();
}

# Compute graphs of xlog cluster statistics
sub pg_xlog_stat_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!scalar keys %all_xlog_stat);

	my %xlog_stat = ();
	foreach my $t (sort {$a <=> $b} keys %all_xlog_stat) {
		$xlog_stat{total} .= '[' . $t . ',' . ($all_xlog_stat{$t}{total} || 0) . '],';
		$xlog_stat{recycled} .= '[' . $t . ',' . ($all_xlog_stat{$t}{recycled} || 0) . '],';
		$xlog_stat{written}  .= '[' . $t . ',' . ($all_xlog_stat{$t}{written} || 0) . '],';
		$xlog_stat{max_wal}  .= '[' . $t . ',' . ($all_xlog_stat{$t}{max_wal} || 0) . '],';
	}
	%all_xlog_stat = ();

	if ($xlog_stat{total} ) {
		my $id = &get_data_id('database-xlog_files', %data_info);
		$xlog_stat{total} =~ s/,$//;
		if (exists $xlog_stat{recycled}) {
			push(@{$data_info{$id}{legends}}, 'recycled', 'written', 'max_wal');
			print &flotr2_linegraph_array($IDX++, 'cluster-xlog_files', \%{$data_info{$id}}, '', $xlog_stat{total}, $xlog_stat{recycled}, $xlog_stat{written}, $xlog_stat{max_wal});
		} else {
			print &flotr2_linegraph_array($IDX++, 'cluster-xlog_files', \%{$data_info{$id}}, '', $xlog_stat{total});
		}
	}
}

# Compute statistics of bgwriter cluster
sub pg_stat_bgwriter
{
	my ($in_dir, $file, $interval) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my @start_vals = ();
	my %total_count = ();
	my $tmp_val = 0;
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		push(@start_vals, @data) if ($#start_vals < 0);
		(($data[1] - $start_vals[1]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[1] - $start_vals[1]);
		$all_stat_bgwriter{$data[0]}{checkpoints_timed} = $tmp_val;
		(($data[2] - $start_vals[2]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[2] - $start_vals[2]);
		$all_stat_bgwriter{$data[0]}{checkpoints_req} .= $tmp_val;
		my $id = 0;
		if ($#data > 10) {
			$id += 2;
			(($data[3] - $start_vals[3]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[3] - $start_vals[3]);
			$all_stat_bgwriter{$data[0]}{checkpoint_write_time} .= $tmp_val;
			(($data[4] - $start_vals[4]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[4] - $start_vals[4]);
			$all_stat_bgwriter{$data[0]}{checkpoint_sync_time} .= $tmp_val;
		}
		(($data[3+$id] - $start_vals[3+$id]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[3+$id] - $start_vals[3+$id]);
		$all_stat_bgwriter{$data[0]}{buffers_checkpoint} .= sprintf("%.2f", $tmp_val/$interval);
		(($data[4+$id] - $start_vals[4+$id]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[4+$id] - $start_vals[4+$id]);
		$all_stat_bgwriter{$data[0]}{buffers_clean} .= sprintf("%.2f", $tmp_val/$interval);
		(($data[5+$id] - $start_vals[5+$id]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[5+$id] - $start_vals[5+$id]);
		$all_stat_bgwriter{$data[0]}{maxwritten_clean} .= sprintf("%.2f", $tmp_val/$interval);
		(($data[6+$id] - $start_vals[6+$id]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[6+$id] - $start_vals[6+$id]);
		$all_stat_bgwriter{$data[0]}{buffers_backend} .= sprintf("%.2f", $tmp_val/$interval);
		(($data[7+$id] - $start_vals[7+$id]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[7+$id] - $start_vals[7+$id]);
		$all_stat_bgwriter{$data[0]}{buffers_backend_fsync} .= sprintf("%.2f", $tmp_val/$interval);
		@start_vals = ();
		push(@start_vals, @data);
	}
	$curfh->close();

}

# Compute graphs of bgwriter cluster statistics
sub pg_stat_bgwriter_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!scalar keys %all_stat_bgwriter);

	my %bgwriter_stat = ();
	foreach my $t (sort {$a <=> $b} keys %all_stat_bgwriter) {
		$bgwriter_stat{checkpoints_timed} .= '[' . $t . ',' . $all_stat_bgwriter{$t}{checkpoints_timed} . '],';
		$bgwriter_stat{checkpoints_req} .= '[' . $t . ',' . $all_stat_bgwriter{$t}{checkpoints_req} . '],';
		$bgwriter_stat{checkpoint_write_time} .= '[' . $t . ',' . ($all_stat_bgwriter{$t}{checkpoint_write_time}||0) . '],';
		$bgwriter_stat{checkpoint_sync_time} .= '[' . $t . ',' . ($all_stat_bgwriter{$t}{checkpoint_sync_time}||0) . '],';
		$bgwriter_stat{buffers_checkpoint} .= '[' . $t . ',' . $all_stat_bgwriter{$t}{buffers_checkpoint} . '],';
		$bgwriter_stat{buffers_clean} .= '[' . $t . ',' . $all_stat_bgwriter{$t}{buffers_clean} . '],';
		$bgwriter_stat{maxwritten_clean} .= '[' . $t . ',' . $all_stat_bgwriter{$t}{maxwritten_clean} . '],';
		$bgwriter_stat{buffers_backend} .= '[' . $t . ',' . $all_stat_bgwriter{$t}{buffers_backend} . '],';
		$bgwriter_stat{buffers_backend_fsync} .= '[' . $t . ',' . $all_stat_bgwriter{$t}{buffers_backend_fsync} . '],';
	}
	%all_stat_bgwriter = ();

	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		next if ($data_info{$id}{name} ne $REAL_ACTION);
		if ($data_info{$id}{name} eq 'database-checkpoints') {
			$bgwriter_stat{checkpoints_timed} =~ s/,$//;
			$bgwriter_stat{checkpoints_req} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'cluster-checkpoints', \%{$data_info{$id}}, '', $bgwriter_stat{checkpoints_timed}, $bgwriter_stat{checkpoints_req});
		} elsif ($data_info{$id}{name} eq 'database-checkpoints_time') {
			if (exists $bgwriter_stat{checkpoint_write_time}) {
				$bgwriter_stat{checkpoint_sync_time} =~ s/,$//;
				$bgwriter_stat{checkpoint_write_time} =~ s/,$//;
				print &flotr2_linegraph_array($IDX++, 'cluster-checkpoints_time', \%{$data_info{$id}}, '', $bgwriter_stat{checkpoint_write_time}, $bgwriter_stat{checkpoint_sync_time});
			}
		} elsif ($data_info{$id}{name} eq 'database-bgwriter') {
			$bgwriter_stat{buffers_checkpoint} =~ s/,$//;
			$bgwriter_stat{buffers_clean} =~ s/,$//;
			$bgwriter_stat{buffers_backend} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'cluster-bgwriter', \%{$data_info{$id}}, '', $bgwriter_stat{buffers_checkpoint}, $bgwriter_stat{buffers_clean}, $bgwriter_stat{buffers_backend}, $bgwriter_stat{maxwritten_clean});
		} elsif ($data_info{$id}{name} eq 'database-bgwriter_count') {
			$bgwriter_stat{maxwritten_clean} =~ s/,$//;
			$bgwriter_stat{buffers_backend_fsync} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'cluster-bgwriter_count', \%{$data_info{$id}}, '',  $bgwriter_stat{maxwritten_clean}, $bgwriter_stat{buffers_backend_fsync});
		}
	}
}

# Compute statistics of connections
sub pg_stat_connections
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my @start_vals = ();
	my $tmp_val = 0;
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data, 5));

		# timestamp | total | active | waiting | idle_in_xact | datname

		push(@global_databases, $data[5]) if (!grep(/^$data[5]$/, @global_databases));
		$all_stat_connections{$data[0]}{$data[5]}{total} = $data[1];
		$all_stat_connections{$data[0]}{$data[5]}{active} = $data[2];
		$all_stat_connections{$data[0]}{$data[5]}{waiting} = $data[3];
		$all_stat_connections{$data[0]}{$data[5]}{idle_in_xact} = $data[4];
		$all_stat_connections{$data[0]}{$data[5]}{idle} = ($data[1] - $data[2] - $data[4]);

		$all_stat_connections{$data[0]}{'all'}{total} += $data[1];
		$all_stat_connections{$data[0]}{'all'}{active} += $data[2];
		$all_stat_connections{$data[0]}{'all'}{waiting} += $data[3];
		$all_stat_connections{$data[0]}{'all'}{idle_in_xact} += $data[4];
		$all_stat_connections{$data[0]}{'all'}{idle} += ($data[1] - $data[2] - $data[4]);
	}
	$curfh->close();
	push(@global_databases, 'all') if (($#global_databases >= 0) && !grep(/^all$/, @global_databases));
}

# Compute graphs of connections statistics
sub pg_stat_connections_report
{
	my ($interval, $src_base, $db_glob, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %connections_stat = ();
	foreach my $time (sort {$a <=> $b} keys %all_stat_connections) {
		foreach my $db (@global_databases) {
			next if (($db_glob ne 'all') && ($db ne $db_glob));
			next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
			$connections_stat{$db}{total} .= '[' . $time . ',' . ($all_stat_connections{$time}{$db}{total}||0) . '],';
			$connections_stat{$db}{active} .= '[' . $time . ',' . ($all_stat_connections{$time}{$db}{active}||0) . '],';
			$connections_stat{$db}{waiting} .= '[' . $time . ',' . ($all_stat_connections{$time}{$db}{waiting}||0) . '],';
			$connections_stat{$db}{idle_in_xact} .= '[' . $time . ',' . ($all_stat_connections{$time}{$db}{idle_in_xact}||0) . '],';
			$connections_stat{$db}{idle} .= '[' . $time . ',' . ($all_stat_connections{$time}{$db}{idle}||0) . '],';
		}
	}
	%all_stat_connections = ();

	my $id = &get_data_id('database-connections', %data_info);
	if (scalar keys %connections_stat > 0) {
		foreach my $db (sort keys %connections_stat) {
			next if ($db ne $db_glob);
			next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
			$connections_stat{$db}{total} =~ s/,$//;
			$connections_stat{$db}{active} =~ s/,$//;
			$connections_stat{$db}{waiting} =~ s/,$//;
			$connections_stat{$db}{idle_in_xact} =~ s/,$//;
			$connections_stat{$db}{idle} =~ s/,$//;
			if ($db ne 'all') {
				print &flotr2_linegraph_array($IDX++, 'database-connections', \%{$data_info{$id}}, $db, $connections_stat{$db}{active}, $connections_stat{$db}{idle}, $connections_stat{$db}{idle_in_xact}, $connections_stat{$db}{waiting});
			} else {
				print &flotr2_linegraph_array($IDX++, 'cluster-connections', \%{$data_info{$id}}, 'all', $connections_stat{$db}{active}, $connections_stat{$db}{idle}, $connections_stat{$db}{idle_in_xact}, $connections_stat{$db}{waiting});
			}
		}
	} else {
		print &empty_dataset('database-connections', \%{$data_info{$id}}, 'indexes');
	}
}

# Compute statistics of user functions call
sub pg_stat_user_functions
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my @start_vals = ();
	my $tmp_val = 0;
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | datname | funcid | schemaname | funcname | calls | total_time | self_time

		next if (($#INCLUDE_DB >= 0) && (!grep($data[1] =~ /^$_$/, @INCLUDE_DB)));

		push(@start_vals, @data) if ($#start_vals < 0);

		$data[4] = "$data[3].$data[4]";

		(($data[5] - $start_vals[5]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[5] - $start_vals[5]);
		$all_stat_user_functions{$data[1]}{$data[4]}{calls} += $tmp_val;
		(($data[6] - $start_vals[6]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[6] - $start_vals[6]);
		$all_stat_user_functions{$data[1]}{$data[4]}{total_time} += $tmp_val;
		(($data[7] - $start_vals[7]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[7] - $start_vals[7]);
		$all_stat_user_functions{$data[1]}{$data[4]}{self_time} += $tmp_val;

		@start_vals = ();
		push(@start_vals, @data);
	}
	$curfh->close();
}

# Compute graphs of user functions call statistics
sub pg_stat_user_functions_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!$db);

	my $id = &get_data_id('database-functions', %data_info);
	my $table_header = qq{
					<th>Schema.function</th>
					<th>Calls</th>
					<th>Total time</th>
					<th>Self time</th>
};
	if (!exists $all_stat_user_functions{$db} || scalar keys %{$all_stat_user_functions{$db}} == 0) {
		$table_header = qq{<td><div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div></td>};
	}
	my $colspan =  ' colspan="4"';
	print qq{
<ul id="slides">
<li class="slide active-slide" id="database-functions-slide">
<div id="database-functions"><br/><br/><br/><br/></div>
<div class="row">
    <div class="col-md-12">
      <div class="panel panel-default">
      <div class="panel-heading">
	<h2><i class="icon-time"></i> $data_info{$id}{menu} on $db database</h2>
	<p>$data_info{$id}{description}</p>
      </div>
      <div class="panel-body">
	<div class="analysis-item row-fluid" id="$db-$data_info{$id}{name}">
		<div class="span11">
			<table class="table table-striped sortable" id="$db-$data_info{$id}{name}-table">
				<thead>
					<tr>
					$table_header
					</tr>
				</thead>
				<tbody>
};
		my $found_fct_stat = 0;
		foreach my $fct (sort keys %{$all_stat_user_functions{$db}}) {
			if (!$all_stat_user_functions{$db}{$fct}{calls} && !$all_stat_user_functions{$db}{$fct}{total_time} && !$all_stat_user_functions{$db}{$fct}{self_time}) {
				next;
			}
			foreach ('calls','total_time','self_time') {
				$all_stat_user_functions{$db}{$fct}{$_} ||= 0;
			}
			print "<tr><th>$fct</th><td>$all_stat_user_functions{$db}{$fct}{calls}</td><td>" . &format_duration($all_stat_user_functions{$db}{$fct}{total_time}) . "</td><td>" . &format_duration($all_stat_user_functions{$db}{$fct}{self_time}) . "</td></tr>\n";
		}
		print qq{
				</tbody>
			</table>
		</div>
	</div>
	</div>
    </div>
</div>
</div>
</li>
</ul>
};

}

# Compute graphs of replication cluster statistics
sub pg_stat_replication
{
	my ($in_dir, $file, $interval) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my @start_vals = ();
	my $tmp_val = 0;
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));
		# timestamp | pid | usesysid | usename | application_name | client_addr | client_hostname | client_port | backend_start | state | master_location | sent_location | write_location | flush_location | replay_location | sync_priority | sync_state
		# Do not care about BACKUP and pg_basebackup connection
		if ( (uc($data[9]) eq 'STREAMING') || (uc($data[4]) eq 'WALRECEIVER') ) {
			push(@start_vals, @data) if ($#start_vals < 0);
			my $name = $data[5];
			$data[6] =~ s/"//g;
			$name .= " - $data[6]" if ($data[6]);
			$all_stat_replication{$data[0]}{master_location} = &getNumericalOffset($data[10]) - &getNumericalOffset($start_vals[10]) if (!$all_stat_replication{$data[0]}{master_location});
			next if (!$data[14] && !$data[11] && !$data[12] && !$data[13]);
			((&getNumericalOffset($data[10]) - &getNumericalOffset($data[14])) < 0) ? $tmp_val = 0 : $tmp_val = (&getNumericalOffset($data[10]) - &getNumericalOffset($data[14]));
			$all_stat_replication{$data[0]}{$name}{replay_location} = sprintf("%.2f", ($tmp_val/$interval));
			((&getNumericalOffset($data[10]) - &getNumericalOffset($data[11])) < 0) ? $tmp_val = 0 : $tmp_val = (&getNumericalOffset($data[10]) - &getNumericalOffset($data[11]));
			$all_stat_replication{$data[0]}{$name}{sent_location} = sprintf("%.2f", ($tmp_val/$interval));
			((&getNumericalOffset($data[10]) - &getNumericalOffset($data[12])) < 0) ? $tmp_val = 0 : $tmp_val = (&getNumericalOffset($data[10]) - &getNumericalOffset($data[12]));
			$all_stat_replication{$data[0]}{$name}{write_location} = sprintf("%.2f", ($tmp_val/$interval));
			((&getNumericalOffset($data[10]) - &getNumericalOffset($data[13])) < 0) ? $tmp_val = 0 : $tmp_val = (&getNumericalOffset($data[10]) - &getNumericalOffset($data[13]));
			$all_stat_replication{$data[0]}{$name}{flush_location} = sprintf("%.2f", ($tmp_val/$interval));

			@start_vals = ();
			push(@start_vals, @data);
		}
	}
	$curfh->close();
}

# Compute graphs of replication cluster statistics
sub pg_stat_replication_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %xlog_stat = ();
	foreach my $t (sort {$a <=> $b} keys %all_stat_replication) {
		foreach my $name (sort {$a cmp $b} keys %{$all_stat_replication{$t}}) {
			if ($name eq 'master_location') {
				$all_stat_replication{$t}{master_location} ||= 0;
				$xlog_stat{master_location} .= '[' . $t . ',' . sprintf("%0.2f", ($all_stat_replication{$t}{master_location}/$interval)) . '],';
				next;
			}
			$xlog_stat{$name}{replay_location} .= '[' . $t . ',' . ($all_stat_replication{$t}{$name}{replay_location} || 0) . '],';
			$xlog_stat{$name}{sent_location} .= '[' . $t . ',' . ($all_stat_replication{$t}{$name}{sent_location} || 0) . '],';
			$xlog_stat{$name}{write_location} .= '[' . $t . ',' . ($all_stat_replication{$t}{$name}{write_location} || 0) . '],';
			$xlog_stat{$name}{flush_location} .= '[' . $t . ',' . ($all_stat_replication{$t}{$name}{flush_location} || 0) . '],';
		}
	}
	%all_stat_replication = ();
	return if (scalar keys %xlog_stat == 0);

	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		next if ($data_info{$id}{name} ne $REAL_ACTION);
		if (exists $xlog_stat{master_location} && ($data_info{$id}{name} eq 'database-xlog')) {
			$xlog_stat{master_location} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'cluster-xlog', \%{$data_info{$id}}, '', $xlog_stat{master_location});
			delete $xlog_stat{master_location};

		} elsif ($data_info{$id}{name} eq 'database-replication') {
			foreach my $host (sort {$a cmp $b} keys %xlog_stat) {
				next if ($host eq 'master_location');
				$xlog_stat{$host}{sent_location} =~ s/,$//;
				$xlog_stat{$host}{write_location} =~ s/,$//;
				$xlog_stat{$host}{flush_location} =~ s/,$//;
				$xlog_stat{$host}{replay_location} =~ s/,$//;
				print &flotr2_linegraph_array($IDX++, 'cluster-replication', \%{$data_info{$id}}, $host, $xlog_stat{$host}{sent_location}, $xlog_stat{$host}{write_location}, $xlog_stat{$host}{replay_location});
			}
		}
	}
}

# Compute statistics of pgbouncer
sub pgbouncer_stats
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));
		next if ($data[1] eq 'pgbouncer');

		# timestamp|database|user|cl_active|cl_waiting|sv_active|sv_idle|sv_used|sv_tested|sv_login|maxwait
		$all_pgbouncer_stats{$data[0]}{$data[1]}{$data[2]}{cl_active} += ($data[3] || 0);
		$all_pgbouncer_stats{$data[0]}{$data[1]}{$data[2]}{cl_waiting} += ($data[4] || 0);
		$all_pgbouncer_stats{$data[0]}{$data[1]}{$data[2]}{sv_active} += ($data[5] || 0);
		$all_pgbouncer_stats{$data[0]}{$data[1]}{$data[2]}{sv_idle} += ($data[6] || 0);
		$all_pgbouncer_stats{$data[0]}{$data[1]}{$data[2]}{sv_used} += ($data[7] || 0);
		$all_pgbouncer_stats{$data[0]}{$data[1]}{$data[2]}{sv_tested} += ($data[8] || 0);
		$all_pgbouncer_stats{$data[0]}{$data[1]}{$data[2]}{sv_login} += ($data[9] || 0);
		$all_pgbouncer_stats{$data[0]}{$data[1]}{$data[2]}{maxwait} += ($data[10] || 0);
	}
	$curfh->close();
}

# Compute graphs of pgbouncer statistics
sub pgbouncer_stats_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %pgbouncer_stat = ();
	my %total_pool = ();
	foreach my $t (sort {$a <=> $b} keys %all_pgbouncer_stats) {
		foreach my $db (keys %{$all_pgbouncer_stats{$t}}) {
			foreach my $usr (keys %{$all_pgbouncer_stats{$t}{$db}}) {
				$pgbouncer_stat{"$db/$usr"}{cl_active} .= '[' . $t . ',' . ($all_pgbouncer_stats{$t}{$db}{$usr}{cl_active} || 0) . '],';
				$pgbouncer_stat{"$db/$usr"}{cl_waiting} .= '[' . $t . ',' . ($all_pgbouncer_stats{$t}{$db}{$usr}{cl_waiting} || 0) . '],';
				$pgbouncer_stat{"$db/$usr"}{sv_active} .= '[' . $t . ',' . ($all_pgbouncer_stats{$t}{$db}{$usr}{sv_active} || 0) . '],';
				$pgbouncer_stat{"$db/$usr"}{sv_idle} .= '[' . $t . ',' . ($all_pgbouncer_stats{$t}{$db}{$usr}{sv_idle} || 0) . '],';
				$pgbouncer_stat{"$db/$usr"}{sv_used} .= '[' . $t . ',' . ($all_pgbouncer_stats{$t}{$db}{$usr}{sv_used} || 0) . '],';
				$pgbouncer_stat{"$db/$usr"}{sv_tested} .= '[' . $t . ',' . ($all_pgbouncer_stats{$t}{$db}{$usr}{sv_tested} || 0) . '],';
				$pgbouncer_stat{"$db/$usr"}{sv_login} .= '[' . $t . ',' . ($all_pgbouncer_stats{$t}{$db}{$usr}{sv_login} || 0) . '],';
				$pgbouncer_stat{"$db/$usr"}{maxwait} .= '[' . $t . ',' . ($all_pgbouncer_stats{$t}{$db}{$usr}{maxwait} || 0) . '],';
				$total_pool{$db}{cl_active} += $all_pgbouncer_stats{$t}{$db}{$usr}{cl_active};
				$total_pool{$db}{cl_waiting} += $all_pgbouncer_stats{$t}{$db}{$usr}{cl_waiting};
				$total_pool{$db}{sv_active} += $all_pgbouncer_stats{$t}{$db}{$usr}{sv_active};
				$total_pool{$db}{sv_idle} += $all_pgbouncer_stats{$t}{$db}{$usr}{sv_idle};
				$total_pool{$db}{sv_used} += $all_pgbouncer_stats{$t}{$db}{$usr}{sv_used};
				$total_pool{$db}{sv_tested} += $all_pgbouncer_stats{$t}{$db}{$usr}{sv_tested};
				$total_pool{$db}{sv_login} += $all_pgbouncer_stats{$t}{$db}{$usr}{sv_login};
				$total_pool{$db}{maxwait} += $all_pgbouncer_stats{$t}{$db}{$usr}{maxwait};
			}
			$pgbouncer_stat{$db}{cl_active} .= '[' . $t . ',' . ($total_pool{$db}{cl_active} || 0) . '],';
			$pgbouncer_stat{$db}{cl_waiting} .= '[' . $t . ',' . ($total_pool{$db}{cl_waiting} || 0) . '],';
			$pgbouncer_stat{$db}{sv_active} .= '[' . $t . ',' . ($total_pool{$db}{sv_active} || 0) . '],';
			$pgbouncer_stat{$db}{sv_idle} .= '[' . $t . ',' . ($total_pool{$db}{sv_idle} || 0) . '],';
			$pgbouncer_stat{$db}{sv_used} .= '[' . $t . ',' . ($total_pool{$db}{sv_used} || 0) . '],';
			$pgbouncer_stat{$db}{sv_tested} .= '[' . $t . ',' . ($total_pool{$db}{sv_tested} || 0) . '],';
			$pgbouncer_stat{$db}{sv_login} .= '[' . $t . ',' . ($total_pool{$db}{sv_login} || 0) . '],';
			$pgbouncer_stat{$db}{maxwait} .= '[' . $t . ',' . ($total_pool{$db}{maxwait} || 0) . '],';
#			$total_pool{'all'}{cl_active} += $total_pool{$db}{cl_active};
#			$total_pool{'all'}{cl_waiting} += $total_pool{$db}{cl_waiting};
#			$total_pool{'all'}{sv_active} += $total_pool{$db}{sv_active};
#			$total_pool{'all'}{sv_idle} += $total_pool{$db}{sv_idle};
#			$total_pool{'all'}{sv_used} += $total_pool{$db}{sv_used};
#			$total_pool{'all'}{sv_tested} += $total_pool{$db}{sv_tested};
#			$total_pool{'all'}{sv_login} += $total_pool{$db}{sv_login};
#			$total_pool{'all'}{maxwait} += $total_pool{$db}{maxwait};
			delete $total_pool{$db};
		}
#		$pgbouncer_stat{'all'}{cl_active} .= '[' . $t . ',' . ($total_pool{'all'}{cl_active} || 0) . '],';
#		$pgbouncer_stat{'all'}{cl_waiting} .= '[' . $t . ',' . ($total_pool{'all'}{cl_waiting} || 0) . '],';
#		$pgbouncer_stat{'all'}{sv_active} .= '[' . $t . ',' . ($total_pool{'all'}{sv_active} || 0) . '],';
#		$pgbouncer_stat{'all'}{sv_idle} .= '[' . $t . ',' . ($total_pool{'all'}{sv_idle} || 0) . '],';
#		$pgbouncer_stat{'all'}{sv_used} .= '[' . $t . ',' . ($total_pool{'all'}{sv_used} || 0) . '],';
#		$pgbouncer_stat{'all'}{sv_tested} .= '[' . $t . ',' . ($total_pool{'all'}{sv_tested} || 0) . '],';
#		$pgbouncer_stat{'all'}{sv_login} .= '[' . $t . ',' . ($total_pool{'all'}{sv_login} || 0) . '],';
#		$pgbouncer_stat{'all'}{maxwait} .= '[' . $t . ',' . ($total_pool{'all'}{maxwait} || 0) . '],';
	}

	# Build graph dataset for all pgbouncer pool
	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		foreach my $db (sort {$a cmp $b} keys %pgbouncer_stat) {
			next if ($DATABASE && ($db ne $DATABASE));
			next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
			next if ($db eq 'all');
			next if ($db =~ /\//);
			if ($data_info{$id}{name} eq 'pgbouncer-connections') {
				$pgbouncer_stat{$db}{cl_active} =~ s/,$//;
				$pgbouncer_stat{$db}{cl_waiting} =~ s/,$//;
				$pgbouncer_stat{$db}{sv_active} =~ s/,$//;
				$pgbouncer_stat{$db}{sv_idle} =~ s/,$//;
				$pgbouncer_stat{$db}{sv_used} =~ s/,$//;
				$pgbouncer_stat{$db}{maxwait} =~ s/,$//;
				print &flotr2_linegraph_array($IDX++, 'pgbouncer-connections', \%{$data_info{$id}}, $db, $pgbouncer_stat{$db}{cl_active}, $pgbouncer_stat{$db}{cl_waiting}, $pgbouncer_stat{$db}{sv_active}, $pgbouncer_stat{$db}{sv_idle},$pgbouncer_stat{$db}{sv_used}, $pgbouncer_stat{$db}{maxwait});
				foreach my $pool (sort {$a cmp $b} keys %pgbouncer_stat) {
					next if ($pool !~ /^$db\//);
					$pgbouncer_stat{$pool}{cl_active} =~ s/,$//;
					$pgbouncer_stat{$pool}{cl_waiting} =~ s/,$//;
					$pgbouncer_stat{$pool}{sv_active} =~ s/,$//;
					$pgbouncer_stat{$pool}{sv_idle} =~ s/,$//;
					$pgbouncer_stat{$pool}{sv_used} =~ s/,$//;
					$pgbouncer_stat{$pool}{maxwait} =~ s/,$//;
					print &flotr2_linegraph_array($IDX++, 'pgbouncer-connections+', \%{$data_info{$id}}, $pool, $pgbouncer_stat{$pool}{cl_active}, $pgbouncer_stat{$pool}{cl_waiting}, $pgbouncer_stat{$pool}{sv_active}, $pgbouncer_stat{$pool}{sv_idle},$pgbouncer_stat{$pool}{sv_used}, $pgbouncer_stat{$pool}{maxwait});
				}
				print "</li>\n";
			}
		}
	}
}

# Get content of pgbouncer.ini
sub pgbouncer_ini
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if ( (!-e "$in_dir/pgbouncer_stats.csv") || (!-e "$in_dir/pgbouncer_stats.csv.gz") );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (my $l = <$curfh>) {
		chomp($l);
		next if ($l !~ /^[a-z]/);
		$l =~ s/\s*#.*//;
		$all_pgbouncer_ini{content} .= "$l\n";
	}
	$curfh->close();
}

# Show relevant content of pgbouncer.ini
sub pgbouncer_ini_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my $output = $all_pgbouncer_ini{content} || '';
	%all_pgbouncer_ini = ();

	if (!$output) {
		$output = '<div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div>';
	} else {
		$output = "<div style=\"white-space: pre\">\n$output</div>\n";
	}
	my $id = &get_data_id('database-pgbouncer', %data_info);
	print qq{
<ul id="slides">
<li class="slide active-slide" id="cluster-pgbouncer-slide">
      <div id="cluster-pgbouncer"><br><br><br><br></div>
	<div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
		<h2><i class="icon-time"></i> $data_info{$id}{menu}</h2>
		<p>$data_info{$id}{description}</p>
              </div>
              <div class="panel-body">
		<div class="analysis-item row-fluid" id="cluster-pgbouncer-report">
			<div class="span11">
				$output
			</div>
		</div>
	      </div>
	      </div>
	    </div>
	</div>
  </li>
</ul>
};
}

# Collect statistics about pgbouncer queries
sub pgbouncer_req_stats
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));
		next if ($data[1] eq 'pgbouncer');

		# timestamp|database|total_requests|total_received|total_sent|total_query_time|avg_req|avg_recv|avg_sent|avg_query
		$all_pgbouncer_req_stats{$data[0]}{$data[1]}{total_requests} += $data[2];
		$all_pgbouncer_req_stats{$data[0]}{$data[1]}{total_received} += $data[3];
		$all_pgbouncer_req_stats{$data[0]}{$data[1]}{total_sent} += $data[4];
		$all_pgbouncer_req_stats{$data[0]}{$data[1]}{total_query_time} += $data[5];
		$all_pgbouncer_req_stats{$data[0]}{$data[1]}{avg_req} += $data[6];
		$all_pgbouncer_req_stats{$data[0]}{$data[1]}{avg_recv} += $data[7];
		$all_pgbouncer_req_stats{$data[0]}{$data[1]}{avg_sent} += $data[8];
		$all_pgbouncer_req_stats{$data[0]}{$data[1]}{avg_query} += $data[9];
	}
	$curfh->close();
}

# Show report about pgbouncer queries
sub pgbouncer_req_stats_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %pgbouncer_stat = ();
	foreach my $t (sort {$a <=> $b} keys %all_pgbouncer_req_stats) {
		foreach my $db (keys %{$all_pgbouncer_req_stats{$t}}) {
			foreach my $k (keys %{$all_pgbouncer_req_stats{$t}{$db}}) {
				$pgbouncer_stat{$db}{$k} .= '[' . $t . ',' . $all_pgbouncer_req_stats{$t}{$db}{$k} . '],';
			}
		}
	}
	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		foreach my $db (sort {$a cmp $b} keys %pgbouncer_stat) {
			next if ($DATABASE && ($db ne $DATABASE));
			next if ($db eq 'all');
			next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
			if ($data_info{$id}{name} eq 'pgbouncer-duration') {
				$pgbouncer_stat{$db}{avg_query} =~ s/,$//;
				print &flotr2_linegraph_array($IDX++, 'pgbouncer-duration', \%{$data_info{$id}}, $db, $pgbouncer_stat{$db}{avg_query});
			} elsif ($data_info{$id}{name} eq 'pgbouncer-number') {
				$pgbouncer_stat{$db}{avg_req} =~ s/,$//;
				print &flotr2_linegraph_array($IDX++, 'pgbouncer-number', \%{$data_info{$id}}, $db, $pgbouncer_stat{$db}{avg_req});
			}
		}
	}
}

# Compute graphs of object size statistics
sub pg_class_size
{
	my ($in_dir, $file) = @_;

	my %total_class = ();
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));
		if ($data[4] !~ /^[a-zA-Z]$/) {
			print STDERR "WARNING: incompatible type of file pg_class_size.csv, the second field should be the database name\n";
			last;
		}

		# timestamp | dbname | nspname | relname | relkind | reltuples | relpages | relsize

		next if (($#INCLUDE_DB >= 0) && (!grep($data[1] =~ /^$_$/, @INCLUDE_DB)));

		my $size = $data[6]*8192;
		$size = $data[7] if ($#data == 7);
		if ($ACTION eq 'database-info') {
			$total_class{$data[1]}{$data[4]}{"$data[2].$data[3]"} = '';
		} else {
			$all_class_size{$data[1]}{$data[4]}{"$data[2].$data[3]"}{size} = $size;
			$all_class_size{$data[1]}{$data[4]}{"$data[2].$data[3]"}{tuples} = $data[5];
			if ($data[5] > 0) {
				$all_class_size{$data[1]}{$data[4]}{"$data[2].$data[3]"}{width} = sprintf("%.2f", $size/$data[5]);
			} else {
				$all_class_size{$data[1]}{$data[4]}{"$data[2].$data[3]"}{width} = '-';
			}
		}
	}
	$curfh->close();

	if ($ACTION eq 'database-info') {
		foreach my $db (sort keys %total_class) {
			next if ($DATABASE && ($db ne $DATABASE));
			next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
			# Count the number of object
			foreach my $k (sort keys %RELKIND) {
				if (exists $total_class{$db}{$k}) {
					$OVERALL_STATS{'class'}{$db}{$k} = scalar keys %{$total_class{$db}{$k}};
				} else {
					$OVERALL_STATS{'class'}{$db}{$k} = 0;
				}
			}
		}
		%total_class = ();
	}
}

# Compute graphs of object size statistics
sub pg_class_size_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!$db);

	my %data = ();
	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		next if ($data_info{$id}{name} !~ /^(table|index)-/);
		my $table_header = '';
		my $kind = '';
		if ($data_info{$id}{name} eq 'table-size') {
			$kind = 'tables';
			$table_header = qq{
					<th>Object name</th>
					<th>Size</th>
					<th>Tuples</th>
					<th>Avg width</th>
};
		} elsif ($data_info{$id}{name} eq 'index-size') {
			$kind = 'indexes';
			$table_header = qq{
					<th>Object name</th>
					<th>Size</th>
					<th>Tuples</th>
					<th>Avg width</th>
};
		}
		if (scalar keys %{$all_class_size{$db}} == 0) {
			$table_header = qq{<td><div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div></td>};
		}
		print qq{
<ul id="slides">
<li class="slide active-slide" id="$data_info{$id}{name}-slide">
      <div id="$data_info{$id}{name}"><br/><br/><br/><br/></div>
<div class="row">
    <div class="col-md-12">
      <div class="panel panel-default">
      <div class="panel-heading">
	<h2><i class="icon-time"></i> $data_info{$id}{menu} on $db database $kind</h2>
	<p>$data_info{$id}{description}</p>
      </div>
      <div class="panel-body">
	<div class="analysis-item row-fluid" id="$db-$data_info{$id}{name}">
		<div class="span11">
			<table class="table table-striped sortable" id="$db-$data_info{$id}{name}-table">
				<thead>
					<tr>
						$table_header
					</tr>
				</thead>
				<tbody>
};
		my $found_table_stat = 0;
		foreach my $k (sort keys %{$all_class_size{$db}}) {
			next if (($k ne 't') && ($k ne 'r') && ($data_info{$id}{name} eq 'table-size'));
			next if (($k ne 'i') && ($data_info{$id}{name} eq 'index-size'));
			my $colspan = ' colspan="5"';
			foreach my $tb (sort {$all_class_size{$db}{$k}{$b}{size} <=> $all_class_size{$db}{$k}{$a}{size} } keys %{$all_class_size{$db}{$k}}) {
				next if (!$all_class_size{$db}{$k}{$tb}{size} && !$all_class_size{$db}{$k}{$tb}{tuples});
				next if (($#INCLUDE_TB >= 0) && !grep(/^$tb$/, @INCLUDE_TB));
				my $table_data = '';
				if ($data_info{$id}{name} =~ /^(table|index)-size$/) {
					$found_table_stat = 1;
					foreach ('size','tuples','width') {
						$all_class_size{$db}{$k}{$tb}{$_} ||= 0;
					}
					$table_data = "<tr><th>$tb</th><td>" . &pretty_print_size($all_class_size{$db}{$k}{$tb}{size}) . "</td><td>" . int($all_class_size{$db}{$k}{$tb}{tuples}) . "</td><td>$all_class_size{$db}{$k}{$tb}{width}</td></tr>\n";
				}
				if ($table_data) {
					print qq{$table_data} if ($table_data);
				}
			}
			if (!$found_table_stat) {
				print qq{<tr><td$colspan><div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div></td></tr>};
			}
		}
		print qq{
				</tbody>
			</table>
		</div>
	</div>
	</div>
    </div>
   </div>
</div>
</li>
</ul>
};
	}
	
	%all_class_size = ();
}

# Compute graphs of locks statistics
sub pg_stat_locks
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp|database|label|(type|mode|granted)|count

		next if (($#INCLUDE_DB >= 0) && (!grep($data[1] =~ /^$_$/, @INCLUDE_DB)));

		$data[3] = 'granted' if ($data[3] eq 't');
		$data[3] = 'waiting' if ($data[3] eq 'f');
		$all_stat_locks{$data[0]}{$data[1]}{$data[2]}{$data[3]} += $data[4];
	}
	$curfh->close();
}

# Compute graphs of locks statistics
sub pg_stat_locks_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!$db);

	my %locks_stat = ();
	my %legends = ();
	foreach my $t (keys %all_stat_locks) {
		foreach my $lbl (keys %{$all_stat_locks{$t}{$db}}) {
			push(@{$legends{$db}{$lbl}}, 'waiting') if ( grep(/^waiting$/, @{$legends{$db}{$lbl}}) && (${$legends{$db}{$lbl}}[0] eq 'granted') );
			foreach my $k (@{$legends{$db}{$lbl}}) {
				$locks_stat{$db}{$lbl}{$k} .= '[' . $t . ',' . ($all_stat_locks{$t}{$db}{$lbl}{$k}||0) . '],';
			}
		}
	}
	%all_stat_locks = ();
	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		my @graph_data = ();
		if ($data_info{$id}{name} eq 'database-lock-types') {
			foreach my $k (sort keys %{$locks_stat{$db}{lock_type}}) {
				$locks_stat{$db}{lock_type}{$k} =~ s/,$//;
				push(@{$data_info{$id}{legends}}, $k);
				push(@graph_data, $locks_stat{$db}{lock_type}{$k});
			}
			print &flotr2_linegraph_array($IDX++, 'database-lock-types', \%{$data_info{$id}}, $db, @graph_data);
		} elsif ($data_info{$id}{name} eq 'database-lock-modes') {
			foreach my $k (sort keys %{$locks_stat{$db}{lock_mode}}) {
				$locks_stat{$db}{lock_mode}{$k} =~ s/,$//;
				push(@{$data_info{$id}{legends}}, $k);
				push(@graph_data, $locks_stat{$db}{lock_mode}{$k});
			}
			print &flotr2_linegraph_array($IDX++, 'database-lock-modes', \%{$data_info{$id}}, $db, @graph_data);
		} elsif ($data_info{$id}{name} eq 'database-lock-granted') {
			foreach my $k (sort keys %{$locks_stat{$db}{lock_granted}}) {
				$locks_stat{$db}{lock_granted}{$k} =~ s/,$//;
				push(@{$data_info{$id}{legends}}, $k);
				push(@graph_data, $locks_stat{$db}{lock_granted}{$k});
			}
			print &flotr2_linegraph_array($IDX++, 'database-lock-granted', \%{$data_info{$id}}, $db, @graph_data);
		}
	}
}

# Compute statistics about unused index
sub pg_stat_unused_indexes
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | dbname | schemaname | relname | indexrelname | index_code

		next if (($#INCLUDE_DB >= 0) && (!grep($data[1] =~ /^$_$/, @INCLUDE_DB)));

		push(@{$all_stat_unused_indexes{$data[1]}},  [ ($data[2], $data[3], $data[4], $data[5]) ] );
	}
	$curfh->close();
}

# Compute report about unused index
sub pg_stat_unused_indexes_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!$db);

	my $id = &get_data_id('unused-index', %data_info);

	my $table_header = qq{
					<th>Schema</th>
					<th>Table</th>
					<th>Index</th>
					<th>Code</th>
};
	if (!exists $all_stat_unused_indexes{$db} || scalar keys %{$all_stat_unused_indexes{$db}} == 0) {
		$table_header = qq{<td><div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div></td>};
	}
	print qq{
<ul id="slides">
<li class="slide active-slide" id="$data_info{$id}{name}-slide">
      <div id="$data_info{$id}{name}"><br/><br/><br/><br/></div>
<div class="row">
    <div class="col-md-12">
      <div class="panel panel-default">
      <div class="panel-heading">
	<h2><i class="icon-time"></i> $data_info{$id}{menu} on $db database</h2>
	<p>$data_info{$id}{description}</p>
      </div>
      <div class="panel-body">
	<div class="analysis-item row-fluid" id="$db-$data_info{$id}{name}">
		<div class="span11">
			<table class="table table-striped" id="$db-$data_info{$id}{name}-table">
				<thead>
					<tr>
					$table_header
					</tr>
				</thead>
				<tbody>
};
	foreach my $r (@{$all_stat_unused_indexes{$db}}) {
		print '<tr><td>', join('</td><td>', @$r), "</td></tr>\n";
	}
	print qq{
				</tbody>
			</table>
		</div>
	</div>
	</div>
    </div>
</div>
</li>
</ul>
};
	%all_stat_unused_indexes = ();
}

# Compute statistics about redundant index
sub pg_stat_redundant_indexes
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));
		# Do not report indexes when one is partial and not the oher one
		next if (grep(/\bWHERE\b/i, $data[2], $data[3]) == 1);

		# timestamp | dbname | contained | containing

		next if (($#INCLUDE_DB >= 0) && (!grep($data[1] =~ /^$_$/, @INCLUDE_DB)));

		push(@{$all_stat_redundant_indexes{$data[1]}}, [ ($data[2], $data[3]) ] );
	}
	$curfh->close();
}

# Compute report about redundant index
sub pg_stat_redundant_indexes_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!$db);

	my $id = &get_data_id('redundant-index', %data_info);
	my $table_header = qq{
                                        <th>Contained</th>
                                        <th>Containing</th>
};
	if (!exists $all_stat_redundant_indexes{$db} || scalar keys %{$all_stat_redundant_indexes{$db}} == 0) {
		$table_header = qq{<td><div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div></td>};
	}
	print qq{
<ul id="slides">
<li class="slide active-slide" id="$data_info{$id}{name}-slide">
      <div id="$data_info{$id}{name}"><br/><br/><br/><br/></div>
<div class="row">
    <div class="col-md-12">
      <div class="panel panel-default">
      <div class="panel-heading">
	<h2><i class="icon-time"></i> $data_info{$id}{menu} on $db database</h2>
	<p>$data_info{$id}{description}</p>
      </div>
      <div class="panel-body">
	<div class="analysis-item row-fluid" id="$db-$data_info{$id}{name}">
		<div class="span11">
			<table class="table table-striped" id="$db-$data_info{$id}{name}-table">
				<thead>
					<tr>
					$table_header
					</tr>
				</thead>
				<tbody>
};
	foreach my $r (@{$all_stat_redundant_indexes{$db}}) {
		print '<tr><td>', join('</td><td>', @$r), "</td></tr>\n";
	}
	print qq{
				</tbody>
			</table>
		</div>
	</div>
	</div>
    </div>
</div>
</li>
</ul>
};
	%all_stat_redundant_indexes = ();
}

# Compute statistics about missing index
sub pg_stat_missing_fkindexes
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | dbname | relname | ddl

		next if (($#INCLUDE_DB >= 0) && (!grep($data[1] =~ /^$_$/, @INCLUDE_DB)));

		push(@{$all_stat_missing_fkindexes{$data[1]}}, [ ($data[2], $data[3]) ] );
	}
	$curfh->close();
}

# Compute report about missing index
sub pg_stat_missing_fkindexes_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!$db);

	my $id = &get_data_id('missing-index', %data_info);
	my $table_header = qq{
					<th>Table</th>
					<th>Missing index</th>
};
	if (!exists $all_stat_missing_fkindexes{$db} || scalar keys %{$all_stat_missing_fkindexes{$db}} == 0) {
		$table_header = qq{<td><div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div></td>};
	}
	print qq{
<ul id="slides">
<li class="slide active-slide" id="$data_info{$id}{name}-slide">
      <div id="$data_info{$id}{name}"><br/><br/><br/><br/></div>
<div class="row">
    <div class="col-md-12">
      <div class="panel panel-default">
      <div class="panel-heading">
	<h2><i class="icon-time"></i> $data_info{$id}{menu} on $db database</h2>
	<p>$data_info{$id}{description}</p>
      </div>
      <div class="panel-body">
	<div class="analysis-item row-fluid" id="$db-$data_info{$id}{name}">
		<div class="span11">
			<table class="table table-striped" id="$db-$data_info{$id}{name}-table">
				<thead>
					<tr>
					$table_header
					</tr>
				</thead>
				<tbody>
};
	foreach my $r (@{$all_stat_missing_fkindexes{$db}}) {
		print '<tr><td>', join('</td><td>', @$r), "</td></tr>\n";
	}
	print qq{
				</tbody>
			</table>
		</div>
	</div>
	</div>
    </div>
</div>
</li>
</ul>
};
	%all_stat_missing_fkindexes = ();
}

# Get relevant content of postgresql.conf
sub postgresql_conf
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (my $l = <$curfh>) {
		chomp($l);
		next if ($l !~ /^[a-z]/);
		$l =~ s/\s*#.*//;
		$all_postgresql_conf{content} .= "$l\n";
	}
	$curfh->close();
}

# Show content of postgresql.conf
sub postgresql_conf_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my $output = $all_postgresql_conf{content} || '';
	%all_postgresql_conf = ();

	if (!$output) {
		$output = '<div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div>';
	} else {
		$output = "<div style=\"white-space: pre\">\n$output</div>\n";
	}
	my $id = &get_data_id('database-pgconf', %data_info);
	print qq{
<ul id="slides">
<li class="slide active-slide" id="cluster-pgconf-slide">
      <div id="cluster-pgconf"><br><br><br><br></div>
	<div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
		<h2><i class="icon-time"></i> $data_info{$id}{menu}</h2>
		<p>$data_info{$id}{description}</p>
              </div>
              <div class="panel-body">
		<div class="analysis-item row-fluid" id="cluster-pgconf-report">
			<div class="span11">
				$output
			</div>
		</div>
	      </div>
	      </div>
	    </div>
	</div>
  </li>
</ul>
};
}

# Get relevant content of recovery.conf
sub recovery_conf
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (my $l = <$curfh>) {
		chomp($l);
		next if ($l !~ /^[a-z]/);
		$l =~ s/\s*#.*//;
		$all_recovery_conf{content} .= "$l\n";
	}
	$curfh->close();
}

# Show content of recovery.conf
sub recovery_conf_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my $output = $all_recovery_conf{content} || '';
	%all_recovery_conf = ();

	if (!$output) {
		$output = '<div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div>';
	} else {
		$output = "<div style=\"white-space: pre\">\n$output</div>\n";
	}
	my $id = &get_data_id('database-recoveryconf', %data_info);
	print qq{
<ul id="slides">
<li class="slide active-slide" id="cluster-recoveryconf-slide">
      <div id="cluster-recoveryconf"><br><br><br><br></div>
	<div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
		<h2><i class="icon-time"></i> $data_info{$id}{menu}</h2>
		<p>$data_info{$id}{description}</p>
              </div>
              <div class="panel-body">
		<div class="analysis-item row-fluid" id="cluster-ercoveryconf-report">
			<div class="span11">
				$output
			</div>
		</div>
	      </div>
	      </div>
	    </div>
	</div>
  </li>
</ul>
};
}

# Show relevant content of postgresql.auto.conf
sub postgresql_auto_conf
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (my $l = <$curfh>) {
		chomp($l);
		next if ($l !~ /^[a-z]/);
		$l =~ s/\s*#.*//;
		$all_postgresql_auto_conf{content} .= "$l\n";
	}
	$curfh->close();
}

# Show relevant content of postgresql.auto.conf
sub postgresql_auto_conf_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my $output = $all_postgresql_auto_conf{content} || '';
	%all_postgresql_auto_conf = ();

	if (!$output) {
		$output = '<div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div>';
	} else {
		$output = "<div style=\"white-space: pre\">\n$output</div>\n";
	}
	my $id = &get_data_id('database-alterconf', %data_info);
	print qq{
<ul id="slides">
<li class="slide active-slide" id="cluster-alterconf-slide">
      <div id="cluster-alterconf"><br><br><br><br></div>
	<div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
		<h2><i class="icon-time"></i> $data_info{$id}{menu}</h2>
		<p>$data_info{$id}{description}</p>
              </div>
              <div class="panel-body">
		<div class="analysis-item row-fluid" id="cluster-alterconf-report">
			<div class="span11">
				$output
			</div>
		</div>
	      </div>
	      </div>
	    </div>
	</div>
  </li>
</ul>
};
}

# Get relevant content of pg_hba.conf
sub pg_hba_conf
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (my $l = <$curfh>) {
		chomp($l);
		next if ($l !~ /^[a-z]/);
		$l =~ s/\s*#.*//;
		$pg_hba_conf{content} .= "$l\n";
	}
	$curfh->close();
}

# Show content of pg_hba.conf
sub pg_hba_conf_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my $output = $pg_hba_conf{content} || '';
	%pg_hba_conf = ();

	if (!$output) {
		$output = '<div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div>';
	} else {
		$output = "<div style=\"white-space: pre\">\n$output</div>\n";
	}

	my $id = &get_data_id('database-pghba', %data_info);
	print qq{
<ul id="slides">
<li class="slide active-slide" id="cluster-pghba-slide">
      <div id="cluster-pghba"><br><br><br><br></div>

	<div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
		<h2><i class="icon-time"></i> $data_info{$id}{menu}</h2>
		<p>$data_info{$id}{description}</p>
              </div>
              <div class="panel-body">
		<div class="analysis-item row-fluid" id="cluster-pghba-report">
			<div class="span11">
				$output
			</div>
		</div>
	      </div>
	      </div>
	    </div>
	</div>
  </li>
</ul>
};
}

# Get relevant content of pg_ident.conf
sub pg_ident_conf
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (my $l = <$curfh>) {
		chomp($l);
		next if ($l !~ /^[a-z]/);
		$l =~ s/\s*#.*//;
		$pg_ident_conf{content} .= "$l\n";
	}
	$curfh->close();
}

# Show content of pg_ident.conf
sub pg_ident_conf_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my $output = $pg_ident_conf{content} || '';
	%pg_ident_conf = ();

	if (!$output) {
		$output = '<div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div>';
	} else {
		$output = "<div style=\"white-space: pre\">\n$output</div>\n";
	}
	my $id = &get_data_id('database-pgident', %data_info);
	print qq{
<ul id="slides">
<li class="slide active-slide" id="cluster-pgident-slide">
      <div id="cluster-pgident"><br><br><br><br></div>

	<div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
		<h2><i class="icon-time"></i> $data_info{$id}{menu}</h2>
		<p>$data_info{$id}{description}</p>
              </div>
              <div class="panel-body">
		<div class="analysis-item row-fluid" id="cluster-pgident-report">
			<div class="span11">
				$output
			</div>
		</div>
	      </div>
	      </div>
	    </div>
	</div>
  </li>
</ul>
};
}

# Get configuration from pg_settings
sub pg_settings
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | label | setting | value
		$all_settings{$data[1]}{$data[2]}{value} = $data[3];

		$all_settings{$data[1]}{$data[2]}{unit} = '';
		$all_settings{$data[1]}{$data[2]}{bootval} = '';
		$all_settings{$data[1]}{$data[2]}{resetval} = '';
		if ($#data >= 6) {
			$all_settings{$data[1]}{$data[2]}{unit} = $data[4];
			$all_settings{$data[1]}{$data[2]}{bootval} = $data[7];
			$all_settings{$data[1]}{$data[2]}{resetval} = $data[8];
		}
	}
	$curfh->close();
}

# Show configuration from pg_settings
sub pg_settings_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my $id = &get_data_id('database-settings', %data_info);
	my $output = '';
	if (scalar keys %all_settings == 0) {
		$output = '<div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div>';
	} else {
		foreach my $lbl (sort keys %all_settings) {
			$output .= "<tr><th colspan=\"4\">$lbl</th></tr>\n";
			$output .= "<tr><th>Name</th><th>Current</th><th>Unit</th><th>Reset val</th><th>Boot val</th></tr>\n";
			foreach my $set (sort { lc($a) cmp lc($b) } keys %{$all_settings{$lbl}}) {
				$output .= "<tr><td>$set</td><td>$all_settings{$lbl}{$set}{value}</td><td>$all_settings{$lbl}{$set}{unit}</td>";
				if ($all_settings{$lbl}{$set}{resetval}) {
					$output .= "<td>$all_settings{$lbl}{$set}{resetval}</td>";
				} else {
					$output .= "<td></td>";
				}
				if ($all_settings{$lbl}{$set}{bootval}) {
					$output .= "<td>$all_settings{$lbl}{$set}{bootval}</td>";
				} else {
					$output .= "<td></td>";
				}
				$output .= "</tr>\n";
			}
		}
		$output = "<table class=\"table table-striped\" id=\"$data_info{$id}{name}-table\"><tbody>\n$output</tbody></table>\n";
		%all_settings = ();
	}

	print qq{
<ul id="slides">
<li class="slide active-slide" id="cluster-settings-slide">
      <div id="cluster-settings"><br><br><br><br></div>

	<div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
		<h2><i class="icon-time"></i> $data_info{$id}{menu}</h2>
		<p>$data_info{$id}{description}</p>
              </div>
              <div class="panel-body">
		<div class="analysis-item row-fluid" id="$data_info{$id}{name}-report">
			<div class="span11">
				$output
			</div>
		</div>
		</div>
	    </div>
	    </div>
	</div>
    </li>
</ul>
};

}

# Get configuration from pg_db_role_setting
sub pg_db_role_setting
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | database | role | settings
		$data[1] ||= 'All';
		$data[2] ||= 'All';
		$all_db_role_setting{$data[1]}{$data[2]} = $data[3];
	}
	$curfh->close();
}

# Show configuration from pg_db_role_setting
sub pg_db_role_setting_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my $id = &get_data_id('database-dbrolesetting', %data_info);
	my $output = '';
	if (scalar keys %all_db_role_setting == 0) {
		$output = '<div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div>';
	} else {

		$output = "<table class=\"table table-striped\" id=\"$data_info{$id}{name}-table\"><tbody>\n";
		$output .= "<tr><th>Database</th><th>Role</th><th>Settings</th></tr>\n";
		foreach my $db (sort keys %all_db_role_setting) {
			next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
			foreach my $set (sort { lc($a) cmp lc($b) } keys %{$all_db_role_setting{$db}}) {
				$output .= "<tr><td>$db</td><td>$set</td><td>$all_db_role_setting{$db}{$set}</td></tr>\n";
			}
		}
		$output .= "</tbody></table>\n";
		%all_db_role_setting = ();
	}

	print qq{
<ul id="slides">
<li class="slide active-slide" id="cluster-dbrolesetting-slide">
      <div id="cluster-dbrolesetting"><br><br><br><br></div>

	<div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
		<h2><i class="icon-time"></i> $data_info{$id}{menu}</h2>
		<p>$data_info{$id}{description}</p>
              </div>
              <div class="panel-body">
		<div class="analysis-item row-fluid" id="$data_info{$id}{name}-report">
			<div class="span11">
			$output
			</div>
		</div>
		</div>
	    </div>
	    </div>
	</div>
    </li>
</ul>
};
	%all_db_role_setting = ();
}


# Compute statistics of buffercache database
sub pg_database_buffercache
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		push(@global_databases, $data[1]) if (!grep(/^$data[1]$/, @global_databases));

		# date_trunc | datname | buffers | buffered | buffers % | database %
		$all_database_buffercache{$data[0]}{$data[1]}{shared_buffers_used} = ($data[4]||0);
		$all_database_buffercache{$data[0]}{$data[1]}{database_loaded} = ($data[5]||0);
		$all_database_buffercache{$data[0]}{'all'}{shared_buffers_used} += ($data[4]||0);
		$all_database_buffercache{$data[0]}{'all'}{database_loaded} += ($data[5]||0);
	}
	$curfh->close();

	push(@global_databases, 'all') if (($#global_databases >= 0) && !grep(/^all$/, @global_databases));
}

# Compute report of buffercache database statistics
sub pg_database_buffercache_report
{
	my ($interval, $src_base, $db_glob, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %shared_stat = ();
	foreach my $t (sort keys %all_database_buffercache) {
		foreach my $db (@global_databases) {
			next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
			$shared_stat{$db}{shared_buffers_used} .= '[' . $t . ',' . ($all_database_buffercache{$t}{$db}{shared_buffers_used}||0) . '],';
			$shared_stat{$db}{database_loaded} .= '[' . $t . ',' . ($all_database_buffercache{$t}{$db}{database_loaded}||0) . '],';
		}
	}
	%all_database_buffercache = ();
	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		if ($data_info{$id}{name} eq 'database-buffersused') {
			my @graph_data = ();
			foreach my $db (sort keys %shared_stat) {
				next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
				push(@{$data_info{$id}{legends}}, "% used by $db");
				$shared_stat{$db}{shared_buffers_used} =~ s/,$//;
				push(@graph_data, $shared_stat{$db}{shared_buffers_used});
			}
			print &flotr2_linegraph_array($IDX++, 'cluster-buffersused', \%{$data_info{$id}}, '', @graph_data);
		} elsif ($data_info{$id}{name} eq 'database-databaseloaded') {
			my @graph_data = ();
			foreach my $db (sort keys %shared_stat) {
				next if ($db eq 'all');
				next if (($db ne 'all') && ($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB)));
				push(@{$data_info{$id}{legends}}, "% of $db");
				$shared_stat{$db}{database_loaded} =~ s/,$//;
				push(@graph_data, $shared_stat{$db}{database_loaded});
			}
			print &flotr2_linegraph_array($IDX++, 'cluster-databaseloaded', \%{$data_info{$id}}, '', @graph_data);
		}
	}
}

# Compute statistics of usagecount in shared buffers
sub pg_database_usagecount
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# date_trunc | datname | usagecount | buffer | buffers %
		$all_database_usagecount{$data[0]}{$data[2]} += ($data[4]||0);
	}
	$curfh->close();
}

# Compute graph of usagecount in shared buffers
sub pg_database_usagecount_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %shared_stat = ();
	foreach my $t (sort keys %all_database_usagecount) {
		foreach my $u (sort keys %{$all_database_usagecount{$t}}) {
			$shared_stat{$u}{usagecount} .= '[' . $t . ',' . $all_database_usagecount{$t}{$u} . '],';
		}
	}
	%all_database_usagecount = ();
	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		if ($data_info{$id}{name} eq 'database-usagecount') {
			my @graph_data = ();
			foreach my $u (sort keys %shared_stat) {
				push(@{$data_info{$id}{legends}}, "% of usagecount $u");
				$shared_stat{$u}{usagecount} =~ s/,$//;
				push(@graph_data, $shared_stat{$u}{usagecount});
			}
			print &flotr2_linegraph_array($IDX++, 'cluster-usagecount', \%{$data_info{$id}}, '', @graph_data);
		}
	}
}

# Compute statistics of dirty buffer in cache
sub pg_database_isdirty
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));
		# date_trunc | datname | usagecount | isdirty | buffer | buffers %
		$all_database_isdirty{$data[0]}{$data[2]} += $data[5] if ($data[3] eq 't');
	}
	$curfh->close();
}

# Compute graphs of dirty buffer in cache
sub pg_database_isdirty_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %shared_stat = ();
	foreach my $t (sort keys %all_database_isdirty) {
		foreach my $u (sort keys %{$all_database_isdirty{$t}}) {
			$shared_stat{$u}{usagecount} .= '[' . $t . ',' . $all_database_isdirty{$t}{$u} . '],';
		}
	}
	%all_database_isdirty = ();
	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		if ($data_info{$id}{name} eq 'database-isdirty') {
			my @graph_data = ();
			foreach my $u (sort keys %shared_stat) {
				push(@{$data_info{$id}{legends}}, "% of usagecount $u");
				$shared_stat{$u}{usagecount} =~ s/,$//;
				push(@graph_data, $shared_stat{$u}{usagecount});
			}
			print &flotr2_linegraph_array($IDX++, 'cluster-isdirty', \%{$data_info{$id}}, '', @graph_data);
		}
	}
}

# Compute statistics of archiver
sub pg_stat_archiver
{
	my ($in_dir, $file) = @_;

	my @start_vals = ();
	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		# timestamp | archived_count | last_archived_wal | last_archived_time | failed_count | last_failed_wal | last_failed_time | stats_reset
                push(@start_vals, @data) if ($#start_vals < 0);

		$data[3] =~ s/\..*//;
		$data[6] =~ s/\..*//;
		$data[7] =~ s/\..*//;

		# Get archiver size statistics
		if ( ($ACTION ne 'home') && ($ACTION ne 'database-info') ) {
			my $tmp_val = '';
			(($data[1] - $start_vals[1]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[1] - $start_vals[1]);
			$all_stat_archiver{$data[0]}{archived_count} = $tmp_val;
			(($data[4] - $start_vals[4]) < 0) ? $tmp_val = 0 : $tmp_val = ($data[4] - $start_vals[4]);
			$all_stat_archiver{$data[0]}{failed_count} = $tmp_val;
			$all_stat_archiver{$data[0]}{last_archived_wal} = $data[2];
			$all_stat_archiver{$data[0]}{last_archived_time} = $data[3];
			$all_stat_archiver{$data[0]}{last_failed_wal} = $data[5];
			$all_stat_archiver{$data[0]}{last_failed_time} = $data[6];
			$all_stat_archiver{$data[0]}{stats_reset} = $data[7];
		} else {
			if (!$OVERALL_STATS{'archiver'}{last_archived_time} || ($data[3] gt $OVERALL_STATS{'archiver'}{last_archived_time})) {
				$OVERALL_STATS{'archiver'}{last_archived_wal} = $data[2];
				$OVERALL_STATS{'archiver'}{last_archived_time} = $data[3];
			}
			if (!$OVERALL_STATS{'archiver'}{last_failed_time} || ($data[6] gt $OVERALL_STATS{'archiver'}{last_failed_time})) {
				$OVERALL_STATS{'archiver'}{last_failed_wal} = $data[5];
				$OVERALL_STATS{'archiver'}{last_failed_time} = $data[6];
			}
			if (!$OVERALL_STATS{'archiver'}{stats_reset} || ($data[7] gt $OVERALL_STATS{'archiver'}{stats_reset})) {
				$OVERALL_STATS{'archiver'}{stats_reset} = $data[7];
			}
		}

		@start_vals = ();
		push(@start_vals, @data);
	}
	$curfh->close();
}

# Compute graphs of archiver statistics
sub pg_stat_archiver_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my %archiver_stat = ();
	foreach my $t (sort {$a <=> $b} keys %all_stat_archiver) {
		$archiver_stat{archived_count} .= '[' . $t . ',' . $all_stat_archiver{$t}{archived_count}. '],';
		$archiver_stat{failed_count} .= '[' . $t . ',' . $all_stat_archiver{$t}{failed_count}. '],';
	}
	%all_stat_archiver = ();
	foreach my $id (sort {$a <=> $b} keys %data_info) {
		next if ($id ne $ID_ACTION);
		if ($data_info{$id}{name} eq 'database-archive') {
			print &flotr2_linegraph_array($IDX++, 'cluster-archive', \%{$data_info{$id}}, '', $archiver_stat{archived_count}, $archiver_stat{failed_count});
		}
	}
}

# Compute graphs of statements statistics
sub pg_stat_statements
{
	my ($in_dir, $file) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	my $total_val = 0;
	my @start_vals = ();
	my $has_temp = 0;

	# Load data from file
	my $curfh = open_filehdl("$in_dir/$file");
	while (<$curfh>) {
		my @data = split(/;/);
		next if (!&normalize_line(\@data));

		next if (($#INCLUDE_DB >= 0) && (!grep($data[2] =~ /^$_$/, @INCLUDE_DB)));

		# pg 8.4
		# timestamp | userid | datname | query | calls | total_time | rows
		# pg 9.0-9.1
		# timestamp | userid | datname | query | calls | total_time | rows | shared_blks_hit | shared_blks_read | shared_blks_written | local_blks_hit | local_blks_read | local_blks_written | temp_blks_read | temp_blks_written
		# pg 9.2+
		# timestamp | userid | datname | query | calls | total_time | rows | shared_blks_hit | shared_blks_read | shared_blks_dirtied | shared_blks_written | local_blks_hit | local_blks_read | local_blks_dirtied | local_blks_written | temp_blks_read | temp_blks_written | blk_read_time | blk_write_time |

		my $id = 3;
		next if (!$data[$id]);

		$all_stat_statements{$data[2]}{$data[$id]}{calls} += ($data[$id+1] || 0);
		$all_stat_statements{$data[2]}{$data[$id]}{total_time} += ($data[$id+2] || 0);
		$all_stat_statements{$data[2]}{$data[$id]}{rows} += ($data[$id+3] || 0);
		if ($#data > 6) {
			$all_stat_statements{$data[2]}{$data[$id]}{shared_blks_hit} += $data[$id+4];
			$all_stat_statements{$data[2]}{$data[$id]}{shared_blks_read} += $data[$id+5];
			if ($#data < 18) {
				$all_stat_statements{$data[2]}{$data[$id]}{shared_blks_written} += $data[$id+6];
				$all_stat_statements{$data[2]}{$data[$id]}{local_blks_hit} += $data[$id+7];
				$all_stat_statements{$data[2]}{$data[$id]}{local_blks_read} += $data[$id+8];
				$all_stat_statements{$data[2]}{$data[$id]}{local_blks_written} += $data[$id+9];
				$all_stat_statements{$data[2]}{$data[$id]}{temp_blks_read} += $data[$id+10];
				$all_stat_statements{$data[2]}{$data[$id]}{temp_blks_written} += $data[$id+11];
				# This is just a flag, the total_time key is not used but must exists to not generate
				# error on use of unitialised value later. This is ugly but useful
				$all_stat_statements{$data[2]}{has_temp}{total_time} = 1;
			} else {
				$all_stat_statements{$data[2]}{$data[$id]}{shared_blks_dirtied} += ($data[$id+6]*8192);
				$all_stat_statements{$data[2]}{$data[$id]}{shared_blks_written} += $data[$id+7];
				$all_stat_statements{$data[2]}{$data[$id]}{local_blks_hit} += $data[$id+8];
				$all_stat_statements{$data[2]}{$data[$id]}{local_blks_read} += $data[$id+9];
				$all_stat_statements{$data[2]}{$data[$id]}{local_blks_dirtied} += $data[$id+10];
				$all_stat_statements{$data[2]}{$data[$id]}{local_blks_written} += $data[$id+11];
				$all_stat_statements{$data[2]}{$data[$id]}{temp_blks_read} += ($data[$id+12]*8192);
				$all_stat_statements{$data[2]}{$data[$id]}{temp_blks_written} += ($data[$id+13]*8192);
				$all_stat_statements{$data[2]}{$data[$id]}{blk_read_time} += $data[$id+14];
				$all_stat_statements{$data[2]}{$data[$id]}{blk_write_time} += $data[$id+15];
				# This is just a flag, the total_time key is not used but must exists to not generate
				# error on use of unitialised value later. This is ugly but useful
				$all_stat_statements{$data[2]}{has_temp}{total_time} = 2;
				if ($data[$id+14] || $data[$id+15]) {
					$all_stat_statements{$data[2]}{has_temp}{total_time} = 3;
				}
			}
		}

	}
	$curfh->close();
}

# Compute graphs of statements statistics
sub pg_stat_statements_report
{
	my ($interval, $src_base, $db, %data_info) = @_;

	return if ( ($ACTION eq 'home') || ($ACTION eq 'database-info') );

	return if (!$db);

	my $id = &get_data_id('database-queries', %data_info);
	my $header = qq{
					<th>Query</th>
					<th>Calls</th>
					<th>Avg time</th>
					<th>Total time</th>
					<th>Rows</th>
};
	if (exists $all_stat_statements{$db}) {
		if (exists $all_stat_statements{$db}{has_temp}) {
			$header .= qq{<th>Temp blocks written</th>};
		}
		if ($all_stat_statements{$db}{has_temp}{total_time} >= 2) {
			$header .= qq{<th>Blocks read</th><th>Blocks hit</th><th>Blocks dirtied</th><th>Blocks written</th>};
		}
                if ($all_stat_statements{$db}{has_temp}{total_time} == 3) {
                        $header .= qq{<th>I/O time</th>};
                }
	} else {
		$header = qq{<td><div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div></td>};
	}
	print qq{
<li class="slide active-slide" id="database-queries-slide">
<div id="database-queries"><br/><br/><br/><br/></div>

<div class="row">
    <div class="col-md-12">
      <div class="panel panel-default">
      <div class="panel-heading">
	<h2><i class="icon-time"></i> $data_info{$id}{menu} on $db database</h2>
	<p>$data_info{$id}{description}</p>
      </div>
      <div class="panel-body">
	<div class="analysis-item row-fluid" id="$db-$data_info{$id}{name}">
		<div class="span11">
			<table class="table table-striped sortable" id="$db-$data_info{$id}{name}-table">
				<thead>
					<tr>
					$header
					</tr>
				</thead>
				<tbody>
};
		foreach my $q (sort {$all_stat_statements{$db}{$b}{total_time} <=> $all_stat_statements{$db}{$a}{total_time}} keys %{$all_stat_statements{$db}}) {
			next if ($q eq 'has_temp');
			my $additional_cols = '';
			if (exists $all_stat_statements{$db}{has_temp}) {
				$additional_cols = "<td>" .  &pretty_print_number($all_stat_statements{$db}{$q}{temp_blks_written}) . "</td>";
			}
			if ($all_stat_statements{$db}{has_temp}{total_time} == 2) {
				$additional_cols .= "<td>" . &pretty_print_number($all_stat_statements{$db}{$q}{shared_blks_read}) . "</td><td>" . &pretty_print_number($all_stat_statements{$db}{$q}{shared_blks_hit}) . "</td><td>" . &pretty_print_number($all_stat_statements{$db}{$q}{shared_blks_dirtied}) . "</td><td>" . &pretty_print_number($all_stat_statements{$db}{$q}{shared_blks_written}) . "</td>";
			}
			if ($all_stat_statements{$db}{has_temp}{total_time} == 3) {
				$additional_cols .= "<td>" . sprintf("%0.2d", ($all_stat_statements{$db}{$q}{blk_read_time}+$all_stat_statements{$db}{$q}{blk_write_time})/($all_stat_statements{$db}{$q}{calls}||1)) . "</td>";
			}

			my $query = $q;
			$query =~ s/#SMCLN#/;/g;
			print "<tr><th width=\"50%\">$query</th><td>$all_stat_statements{$db}{$q}{calls}</td><td>" . &format_duration(int($all_stat_statements{$db}{$q}{total_time}/($all_stat_statements{$db}{$q}{calls}||1))) . "</td><td>" . &format_duration($all_stat_statements{$db}{$q}{total_time}) . "</td><td>$all_stat_statements{$db}{$q}{rows}</td>$additional_cols</tr>\n";
		}
		print qq{
				</tbody>
			</table>
		</div>
	</div>
	</div>
    </div>
</div>
</div>
</li>
};
	%all_stat_statements = ();

}

sub normalize_line
{
	my $data = shift;

	# Get position of the database name
	my $pos  = shift;
	$pos ||= 2;

	return 0 if ($data->[0] !~ /^\d+/);

	$data->[0] = &convert_time($data->[0]);

	# Skip unwanted lines
	return 0 if ($BEGIN && ($data->[0] < $BEGIN));
	return 0 if ($END   && ($data->[0] > $END));

	chomp($data->[-1]);
	map { s/,/\./g; s/^$/0/; } @$data;

	# Always skip default template database
	return 0 if ($data->[$pos] =~ /template/);

	return 1;
}

sub pretty_print_size
{
        my $val = shift;
        return 0 if (!$val);
	return '-' if ($val eq '-');

        if ($val >= 1125899906842624) {
                $val = ($val / 1125899906842624);
                $val = sprintf("%0.2f", $val) . " PB";
        } elsif ($val >= 1099511627776) {
                $val = ($val / 1099511627776);
                $val = sprintf("%0.2f", $val) . " TB";
        } elsif ($val >= 1073741824) {
                $val = ($val / 1073741824);
                $val = sprintf("%0.2f", $val) . " GB";
        } elsif ($val >= 1048576) {
                $val = ($val / 1048576);
                $val = sprintf("%0.2f", $val) . " MB";
        } elsif ($val >= 1024) {
                $val = ($val / 1024);
                $val = sprintf("%0.2f", $val) . " KB";
        } else {
                $val = $val . " B";
        }

        return $val;
}

sub pretty_print_number
{
        my $val = shift;
        return 0 if (!$val);
	return '-' if ($val eq '-');

        if ($val >= 1000000000000000) {
                $val = ($val / 1000000000000000);
                $val = sprintf("%0.2f", $val) . " P";
        } elsif ($val >= 1000000000000) {
                $val = ($val / 1000000000000);
                $val = sprintf("%0.2f", $val) . " T";
        } elsif ($val >= 1000000000) {
                $val = ($val / 1000000000);
                $val = sprintf("%0.2f", $val) . " G";
        } elsif ($val >= 1000000) {
                $val = ($val / 1000000);
                $val = sprintf("%0.2f", $val) . " M";
        } elsif ($val >= 1000) {
                $val = ($val / 1000);
                $val = sprintf("%0.2f", $val) . " K";
        }

        return $val;
}


sub show_home
{
	my $in_dir = shift();

	# Compute global statistics for home page dashboard
	my %overall_stat_databases = ();
	if (exists $OVERALL_STATS{'cluster'}) {
		$OVERALL_STATS{'cluster'}{'blks_hit'} ||= 0;
		$OVERALL_STATS{'cluster'}{'blks_read'} ||= 0;
		$OVERALL_STATS{'cluster'}{'cache_ratio'} = sprintf("%3d", ($OVERALL_STATS{'cluster'}{'blks_hit'} * 100) / (($OVERALL_STATS{'cluster'}{'blks_read'} + $OVERALL_STATS{'cluster'}{'blks_hit'}) || 1)) . "%";
		$OVERALL_STATS{'cluster'}{'temp_bytes'} = &pretty_print_size($OVERALL_STATS{'cluster'}{'temp_bytes'});
		foreach my $db (keys %{$OVERALL_STATS{'database'}}) {
			next if ($db eq 'all');
			$OVERALL_STATS{'database'}{$db}{'blks_hit'} ||= 0;
			$OVERALL_STATS{'database'}{$db}{'blks_read'} ||= 0;
			$OVERALL_STATS{'database'}{$db}{'blks_hit'} ||= 0;
			$OVERALL_STATS{'database'}{$db}{'cache_ratio'} = sprintf("%3d", ($OVERALL_STATS{'database'}{$db}{'blks_hit'} * 100) / (($OVERALL_STATS{'database'}{$db}{'blks_read'} + $OVERALL_STATS{'database'}{$db}{'blks_hit'}) || 1));
		}
		foreach my $db (keys %{$OVERALL_STATS{'database'}}) {
			next if ($db eq 'all');
			$OVERALL_STATS{'cluster'}{'size'} += $OVERALL_STATS{'database'}{$db}{'size'};
			next if (($#INCLUDE_DB >= 0) && !grep($db =~ /^$_$/, @INCLUDE_DB));
			if (exists $OVERALL_STATS{'database'}{$db}{'size'}) {
				if (!exists $overall_stat_databases{'size'} || $OVERALL_STATS{'database'}{$db}{'size'} > $overall_stat_databases{'size'}[1]) {
					@{$overall_stat_databases{'size'}} = ($db, $OVERALL_STATS{'database'}{$db}{'size'});
				}
			}
			if (exists $OVERALL_STATS{'database'}{$db}{'nbackend'}) {
				if (!exists $overall_stat_databases{'nbackend'} || $OVERALL_STATS{'database'}{$db}{'nbackend'} > $overall_stat_databases{'nbackend'}[1]) {
					@{$overall_stat_databases{'nbackend'}} = ($db, $OVERALL_STATS{'database'}{$db}{'nbackend'});
				}
			}
			if (exists $OVERALL_STATS{'database'}{$db}{'returned'}) {
				if (!exists $overall_stat_databases{'returned'} || $OVERALL_STATS{'database'}{$db}{'returned'} > $overall_stat_databases{'returned'}[1]) {
					@{$overall_stat_databases{'returned'}} = ($db, $OVERALL_STATS{'database'}{$db}{'returned'});
				}
			}
			if (exists $OVERALL_STATS{'database'}{$db}{'temp_files'}) {
				if (!exists $overall_stat_databases{'temp_files'} || $OVERALL_STATS{'database'}{$db} {'temp_files'} > $overall_stat_databases{'temp_files'}[1]) {
					@{$overall_stat_databases{'temp_files'}} = ($db, $OVERALL_STATS{'database'}{$db}{'temp_files'});
				}
			}
			if (exists $OVERALL_STATS{'database'}{$db}{'temp_bytes'}) {
				if (!exists $overall_stat_databases{'temp_bytes'} || $OVERALL_STATS{'database'}{$db}{'temp_bytes'} > $overall_stat_databases{'temp_bytes'}[1]) {
					@{$overall_stat_databases{'temp_bytes'}} = ($db, $OVERALL_STATS{'database'}{$db}{'temp_bytes'});
				}
			}
			if (exists $OVERALL_STATS{'database'}{$db}{'deadlocks'}) {
				if (!exists $overall_stat_databases{'deadlocks'} || $OVERALL_STATS{'database'}{$db}{'deadlocks'} > $overall_stat_databases{'deadlocks'}[1]) {
					@{$overall_stat_databases{'deadlocks'}} = ($db, $OVERALL_STATS{'database'}{$db}{'deadlocks'});
				}
			}
			if (exists $OVERALL_STATS{'database'}{$db}{'cache_ratio'}) {
				if (!exists $overall_stat_databases{'cache_ratio'} || $OVERALL_STATS{'database'}{$db}{'cache_ratio'} < $overall_stat_databases{'cache_ratio'}[1]) {
					@{$overall_stat_databases{'cache_ratio'}} = ($db, $OVERALL_STATS{'database'}{$db}{'cache_ratio'});
				}
			}
		}
		@{$overall_stat_databases{'size'}} = ('unknown', 0) if (!exists $overall_stat_databases{'size'});
		if (exists $overall_stat_databases{'size'}) {
			$overall_stat_databases{'size'}[1] = &pretty_print_size($overall_stat_databases{'size'}[1]);
		}
		if (exists $overall_stat_databases{'temp_bytes'}) {
			$overall_stat_databases{'temp_bytes'}[1] = &pretty_print_size($overall_stat_databases{'temp_bytes'}[1]);
		}
	}

	my %overall_system_stats = ();
	if (!$DISABLE_SAR) {

		if (!exists $OVERALL_STATS{'system'}{'cpu'}) {
			@{$OVERALL_STATS{'system'}{'cpu'}} = ('unknown', 0);
		} else {
			${$OVERALL_STATS{'system'}{'cpu'}}[0] = localtime(${$OVERALL_STATS{'system'}{'cpu'}}[0]/1000);
		}
		if (!exists $OVERALL_STATS{'system'}{'load'}) {
			@{$OVERALL_STATS{'system'}{'load'}} = ('unknown', 0);
		} else {
			${$OVERALL_STATS{'system'}{'load'}}[0] = localtime(${$OVERALL_STATS{'system'}{'load'}}[0]/1000);
		}
		if (!exists $OVERALL_STATS{'system'}{'kbcached'}) {
			@{$OVERALL_STATS{'system'}{'kbcached'}} = ('unknown', 0);
		} else {
			${$OVERALL_STATS{'system'}{'kbcached'}}[0] = localtime(${$OVERALL_STATS{'system'}{'kbcached'}}[0]/1000);
		}
		if (!exists $OVERALL_STATS{'system'}{'bread'}) {
			@{$OVERALL_STATS{'system'}{'bread'}} = ('unknown', 0);
		} else {
			${$OVERALL_STATS{'system'}{'bread'}}[0] = localtime(${$OVERALL_STATS{'system'}{'bread'}}[0]/1000);
		}
		if (!exists $OVERALL_STATS{'system'}{'bwrite'}) {
			@{$OVERALL_STATS{'system'}{'bwrite'}} = ('unknown', 0);
		} else {
			${$OVERALL_STATS{'system'}{'bwrite'}}[0] = localtime(${$OVERALL_STATS{'system'}{'bwrite'}}[0]/1000);
		}
		if (!exists $OVERALL_STATS{'system'}{'svctm'}) {
			@{$OVERALL_STATS{'system'}{'svctm'}} = ('unknown', 0, 'unknown');
		} else {
			${$OVERALL_STATS{'system'}{'svctm'}}[0] = localtime(${$OVERALL_STATS{'system'}{'svctm'}}[0]/1000);
		}
		if (exists $OVERALL_STATS{'system'}{'devices'}) {
			foreach my $d (keys %{$OVERALL_STATS{'system'}{'devices'}}) {
				if (! exists $overall_system_stats{read} || ($overall_system_stats{read}[1] < $OVERALL_STATS{'system'}{'devices'}{$d}{read})) {
					@{$overall_system_stats{read}} = ($d, $OVERALL_STATS{'system'}{'devices'}{$d}{read});
				}
				if (! exists $overall_system_stats{write} || ($overall_system_stats{write}[1] < $OVERALL_STATS{'system'}{'devices'}{$d}{write})) {
					@{$overall_system_stats{write}} = ($d, $OVERALL_STATS{'system'}{'devices'}{$d}{write});
				}
				if (! exists $overall_system_stats{tps} || ($overall_system_stats{tps}[1] < $OVERALL_STATS{'system'}{'devices'}{$d}{tps})) {
					@{$overall_system_stats{tps}} = ($d, $OVERALL_STATS{'system'}{'devices'}{$d}{tps});
				}
			}
		}
		if (!exists $overall_system_stats{read}) {
			@{$overall_system_stats{read}} = ('unknown', 0);
		}
		if (!exists $overall_system_stats{write}) {
			@{$overall_system_stats{write}} = ('unknown', 0);
		}
		if (!exists $overall_system_stats{tps}) {
			@{$overall_system_stats{tps}} = ('unknown', 0);
		}
		$overall_system_stats{read}[1] = &pretty_print_size($overall_system_stats{read}[1]);
		$overall_system_stats{write}[1] = &pretty_print_size($overall_system_stats{write}[1]);

		@{$overall_system_stats{kbcached}} =  ($OVERALL_STATS{'system'}{'kbcached'}[0], &pretty_print_size($OVERALL_STATS{'system'}{'kbcached'}[1]));
		@{$overall_system_stats{bread}} =  ($OVERALL_STATS{'system'}{'bread'}[0], &pretty_print_size($OVERALL_STATS{'system'}{'bread'}[1]));
		@{$overall_system_stats{bwrite}} =  ($OVERALL_STATS{'system'}{'bwrite'}[0], &pretty_print_size($OVERALL_STATS{'system'}{'bwrite'}[1]));
	}

	my $numcol = 4;
	if ($DISABLE_SAR) {
		$numcol = 6;
	} elsif (!exists $OVERALL_STATS{'system'}) {
		$numcol = 12;
	}

	print <<EOF;
<ul id="slides">
<li class="slide active-slide" id="home-slide">
    <div id="home"><br/><br/><br/><br/></div>
EOF
	my $tz = ((0-$STATS_TIMEZONE)*3600);
	if (exists $OVERALL_STATS{'start_date'}) {
		$OVERALL_STATS{'start_date'} = ($OVERALL_STATS{'start_date'}/1000) + $tz;
		$OVERALL_STATS{'end_date'}   = ($OVERALL_STATS{'end_date'}/1000) + $tz;
	}
	my $start_date = gmtime($OVERALL_STATS{'start_date'}||0) || 'Unknown start date';
	my $end_date = gmtime($OVERALL_STATS{'end_date'}||0) || 'Unknown end date';
	if (exists $OVERALL_STATS{'sar_start_date'}) {
		$OVERALL_STATS{'sar_start_date'} = ($OVERALL_STATS{'sar_start_date'}/1000) + $tz;
		$OVERALL_STATS{'sar_end_date'}   = ($OVERALL_STATS{'sar_end_date'}/1000) + $tz;
	}
	my $sar_start_date = gmtime($OVERALL_STATS{'sar_start_date'}||0) || 'Unknown start date';
	my $sar_end_date = gmtime($OVERALL_STATS{'sar_end_date'}||0) || 'Unknown end date';

	if (exists $OVERALL_STATS{'cluster'}) {
		$OVERALL_STATS{'cluster'}{'size'} ||= 0;
		$OVERALL_STATS{'cluster'}{'nbackend'} ||= 0;
		$OVERALL_STATS{'cluster'}{'returned'} ||= 0;
		$OVERALL_STATS{'cluster'}{'cache_ratio'} ||= 0;
		$OVERALL_STATS{'cluster'}{'temp_files'} ||= 0;
		$OVERALL_STATS{'cluster'}{'temp_bytes'} ||= 0;
		$OVERALL_STATS{'cluster'}{'deadlocks'} ||= 0;
		my $temp_file_info = '';
		if ($OVERALL_STATS{'cluster'}{'temp_files'}) {
			$temp_file_info = qq{
		<li><span class="figure">$OVERALL_STATS{'cluster'}{'temp_files'}</span> <span class="figure-label">Temporary files</span></li>
		<li><span class="figure">$OVERALL_STATS{'cluster'}{'temp_bytes'}</span> <span class="figure-label">Temporary files size</span></li>
};
		}
		my $deadlock_info = '';
		if ($OVERALL_STATS{'cluster'}{'deadlocks'}) {
			$deadlock_info = qq{
		<li><span class="figure">$OVERALL_STATS{'cluster'}{'deadlocks'}</span> <span class="figure-label">Deadlocks</span></li>
};
		}
		my $extnum = $#{$OVERALL_STATS{'cluster'}{'extensions'}} + 1;
		my $extensions_info = '';
		if ($extnum) {
			my $extlist = join(', ', @{$OVERALL_STATS{'cluster'}{'extensions'}});
			$extensions_info = qq{<li><span class="figure">$extnum</span> <span class="figure-label">Extensions ($extlist)</span></li>};
		}
		$sysinfo{PGVERSION}{'full_version'} ||= '';
		my $database_number = scalar keys %{$OVERALL_STATS{'database'}};
		$OVERALL_STATS{'cluster'}{'size'} ||= '-';
		$OVERALL_STATS{'cluster'}{'nbackend'} ||= '-';
		$OVERALL_STATS{'cluster'}{'returned'} ||= '-';
		$OVERALL_STATS{'cluster'}{'cache_ratio'} ||= '-';
		my $cluster_size = &pretty_print_size($OVERALL_STATS{'cluster'}{'size'});
		print <<EOF;
      <div class="row">
            <div class="col-md-$numcol">
              <div class="panel panel-default">
              <div class="panel-heading">
              <i class="fa fa-cogs fa-2x pull-left fa-border"></i><h2>Cluster</h2>
              </div>
              <div class="panel-body panel-xlheight">
		<div class="key-figures">
		<span class="figure-date">$start_date to $end_date</span>
		<ul>
		<li></li>
		<li><span class="figure">$cluster_size</span> <span class="figure-label">Cluster size</span></li>
		<li><span class="figure">$database_number</span> <span class="figure-label">Databases</span></li>
		<li><span class="figure">$OVERALL_STATS{'cluster'}{'nbackend'}</span> <span class="figure-label">Connections</span></li>
		<li><span class="figure">$OVERALL_STATS{'cluster'}{'returned'}</span> <span class="figure-label">Tuples returned</span></li>
		<li><span class="figure">$OVERALL_STATS{'cluster'}{'cache_ratio'}</span> <span class="figure-label">Hit cache ratio</span></li>
		$temp_file_info
		$deadlock_info
		$extensions_info
		</ul>
		</div>
              </div>
              </div>
            </div><!--/span-->

            <div class="col-md-$numcol">
              <div class="panel panel-default">
              <div class="panel-heading">
              <i class="fa fa-th fa-2x pull-left fa-border"></i><h2>Databases</h2>
              </div>
              <div class="panel-body panel-xlheight">
		<div class="key-figures">
		<ul>
		<li></li>
EOF
		if (exists $overall_stat_databases{'size'}) {
			print <<EOF;
		<li><span class="figure">$overall_stat_databases{'size'}[1]</span> <span class="figure-label">Largest database</span><br/><span class="figure-date">($overall_stat_databases{'size'}[0])</span></li>
EOF
		}
		if (exists $overall_stat_databases{'nbackend'}) {
			print <<EOF;
		<li><span class="figure">$overall_stat_databases{'nbackend'}[1]</span> <span class="figure-label">Most connections</span><br/><span class="figure-date">($overall_stat_databases{'nbackend'}[0])</span></li>
EOF
		}
		if (exists $overall_stat_databases{'returned'}) {
			print qq{<li><span class="figure">$overall_stat_databases{'returned'}[1]</span> <span class="figure-label">Most tuples returned</span><br/><span class="figure-date">($overall_stat_databases{'returned'}[0])</span></li>
};
		}
		if (exists $overall_stat_databases{'cache_ratio'}) {
			push(@{$overall_stat_databases{'cache_ratio'}}, '-', '-') if ($#{$overall_stat_databases{'cache_ratio'}} < 0);
			print <<EOF;
		<li><span class="figure">$overall_stat_databases{'cache_ratio'}[1]%</span> <span class="figure-label">Worst cache utilization</span><br/><span class="figure-date">($overall_stat_databases{'cache_ratio'}[0])</span></li>
EOF
		}
		if (exists $overall_stat_databases{'temp_files'} && $overall_stat_databases{'temp_files'}[1]) {
			print <<EOF;
		<li><span class="figure">$overall_stat_databases{'temp_files'}[1]</span> <span class="figure-label">Most temporary files</span><br/><span class="figure-date">($overall_stat_databases{'temp_files'}[0])</span></li>
EOF
		}
		if (exists $overall_stat_databases{'temp_bytes'} && $overall_stat_databases{'temp_bytes'}[1]) {
			print <<EOF;
		<li><span class="figure">$overall_stat_databases{'temp_bytes'}[1]</span> <span class="figure-label">Most temporary bytes</span><br/><span class="figure-date">($overall_stat_databases{'temp_bytes'}[0])</span></li>
EOF
		}
		if (exists $overall_stat_databases{'deadlocks'} && $overall_stat_databases{'deadlocks'}[1]) {
			print <<EOF;
		<li><span class="figure">$overall_stat_databases{'deadlocks'}[1]</span> <span class="figure-label">Most deadlocks</span><br/><span class="figure-date">($overall_stat_databases{'deadlocks'}[0])</span></li>
EOF
		}
		print <<EOF;
		</ul>
		</div>
              </div>
              </div>
            </div><!--/span-->
EOF

	}
	if (!$DISABLE_SAR) {
		print <<EOF;
            <div class="col-md-$numcol">
              <div class="panel panel-default">
              <div class="panel-heading">
              <span class="fa-stack fa-lg pull-left fa-border"><i class="fa fa-square fa-stack-2x"></i><i class="fa fa-terminal fa-stack-1x fa-inverse"></i></span> <h2>System</h2>
              </div>
              <div class="panel-body panel-xlheight">
		<div class="key-figures">
		<span class="figure-date">$sar_start_date to $sar_end_date</span>
		<ul>
		<li></li>
		<li><span class="figure">$OVERALL_STATS{'system'}{'cpu'}[1]%</span> <span class="figure-label">Highest CPU utilization</span><br/><span class="figure-date">($OVERALL_STATS{'system'}{'cpu'}[0])</span></li>
		<li><span class="figure">$OVERALL_STATS{'system'}{'load'}[1]</span> <span class="figure-label">Highest system load</span><br/><span class="figure-date">($OVERALL_STATS{'system'}{'load'}[0])</span></li>
		<li><span class="figure">$OVERALL_STATS{'system'}{'svctm'}[1] ms</span> <span class="figure-label">Highest device service time</span><br/><span class="figure-date">($OVERALL_STATS{'system'}{'svctm'}[0] on device $OVERALL_STATS{'system'}{'svctm'}[2])</span></li>
		<li><span class="figure">$overall_system_stats{kbcached}[1]</span> <span class="figure-label">Lowest system cache</span><br/><span class="figure-date">($overall_system_stats{kbcached}[0])</span></li>
		<!-- li><span class="figure">$overall_system_stats{bread}[1]</span> <span class="figure-label">Highest block read</span><br/><span class="figure-date">($overall_system_stats{bread}[0])</span></li -->
		<!-- li><span class="figure">$overall_system_stats{bwrite}[1]</span> <span class="figure-label">Highest block write</span><br/><span class="figure-date">($overall_system_stats{bwrite}[0])</span> </li -->
		<li><span class="figure">$overall_system_stats{read}[1]</span> <span class="figure-label">Most read device</span><br/><span class="figure-date"> ($overall_system_stats{read}[0])</span></li>
		<li><span class="figure">$overall_system_stats{write}[1]</span> <span class="figure-label">Most written device</span><br/><span class="figure-date">($overall_system_stats{write}[0])</span></li>
		<li><span class="figure">$overall_system_stats{tps}[1]</span> <span class="figure-label">Highest tps on device</span><br/><span class="figure-date">($overall_system_stats{tps}[0])</span></li>
		</ul>
		</div>
              </div>
              </div>
            </div><!--/span-->
EOF
	}
	print <<EOF;
      </div>
EOF

	if (exists $OVERALL_STATS{'archiver'}) {
		my $archiver_infos = '';
		if (exists $OVERALL_STATS{'archiver'}{last_archived_wal}) {
			$archiver_infos = qq{<li><span class="figure">$OVERALL_STATS{'archiver'}{last_archived_wal}</span> <span class="figure-label">Last archived wal</span></li>};
			$archiver_infos .= qq{<li><span class="figure">$OVERALL_STATS{'archiver'}{last_archived_time}</span> <span class="figure-label">Last archived time</span></li>};
		}
		if (exists $OVERALL_STATS{'archiver'}{last_failed_wal}) {
			$archiver_infos .= qq{<li><span class="figure">$OVERALL_STATS{'archiver'}{last_failed_wal}</span> <span class="figure-label">Last failed wal</span></li>};
			$archiver_infos .= qq{<li><span class="figure">$OVERALL_STATS{'archiver'}{last_failed_time}</span> <span class="figure-label">Last failed time</span></li>};
		}
		if (exists $OVERALL_STATS{'archiver'}{stats_reset}) {
			$archiver_infos .= qq{<li><span class="figure">$OVERALL_STATS{'archiver'}{stats_reset}</span> <span class="figure-label">Last stats reset</span></li>};
		}

		# Perform some initialization in case
		print <<EOF;
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
              <i class="fa fa-th fa-2x pull-left fa-archive"></i><h2>Archiver</h2>
              </div>
              <div class="panel-body">
		<div class="key-figures">
		<ul>
		<li></li>
		$archiver_infos
		</ul>
		</div>
              </div>
              </div>
            </div><!--/span-->
EOF
	}

	if (exists $sysinfo{PGVERSION}) {
		print <<EOF;

<span class="figure-label">$sysinfo{PGVERSION}{'full_version'}</span>
EOF
	}
	print <<EOF;
</li>
</ul> <!-- end of slides -->
EOF

}

sub wrong_date_selection
{
	print <<EOF;
<ul id="slides">
<li class="slide active-slide" id="wrong_date-slide">

	<div id="wrong_date"><br/><br/><br/><br/><br/></div>
	<div class="jumbotron">
	<h1>No data found</h1>
	<p>$PROGRAM is not able to find any data relative to your date selection.</p>
	<ul>
	<li>Start: $o_year-$o_month-$o_day $o_hour:00:00</li>
	<li>End: $e_year-$e_month-$e_day $e_hour:59:59</li>
	</ul>
	<p>Please choose more accurate dates</p>
	</div>
</li>
</ul> <!-- end of slides -->
EOF

}


sub show_about
{
	print <<EOF;
<ul id="slides">
<li class="slide active-slide" id="about-slide">

	<div id="about"><br/><br/><br/><br/><br/></div>
	<div class="jumbotron">
	<h1>About $PROGRAM</h1>
	<p>$PROGRAM is a Perl program used to perform a full audit of a PostgreSQL Cluster. It is divided in two parts, a collector used to grab statistics on the PostgreSQL cluster using psql and sysstat, a grapher that will generate all HTML output. It is fully open source and free of charge.</p>
	</div>
	<div class="row">
            <div class="col-md-4">
              <div class="panel panel-default">
              <div class="panel-heading">
              <i class="fa fa-chain-broken fa-2x pull-left fa-border"></i><h2>License</h2>
              </div>
              <div class="panel-body panel-height">
              <p>$PROGRAM is licenced under the PostgreSQL Licence a liberal Open Source license, similar to the BSD or MIT licenses.</p>
	      <p>That mean that all parts of the program are open source and free of charge.</p>
	      <p>This is the case for both, the collector and the grapher programs.</p>
              </div>
              </div>
            </div><!--/span-->
            <div class="col-md-4">
              <div class="panel panel-default">
              <div class="panel-heading">
              <i class="fa fa-download fa-2x pull-left fa-border"></i><h2>Download</h2>
              </div>
              <div class="panel-body panel-height">
              <p>Official releases at SourceForge:<br/>
	      [ <a href="http://sourceforge.net/projects/pgcluu/">http://sourceforge.net/projects/pgcluu/</a> ].</p>
	      <p>Source code at github:<br/>
	      [ <a href="https://github.com/darold/pgcluu">https://github.com/darold/pgcluu</a> ].</p>
	      <p>ChangeLog can be read on-line on GitHub repository <a href="https://github.com/darold/pgcluu/blob/master/ChangeLog">here</a>
	      <p>Offical web site is hosted at <a href="http://pgcluu.darold.net/">pgcluu.darold.net</a>
              </div>
              </div>
            </div><!--/span-->
            <div class="col-md-4">
              <div class="panel panel-default">
              <div class="panel-heading">
              <i class="fa fa-wrench fa-2x pull-left fa-border"></i><h2>Authors</h2>
              </div>
              <div class="panel-body panel-height">
	      <p>$PROGRAM is an original development of <a href="http://www.darold.net/">Gilles Darold</a>.</p>
	      <p>Some parts of the collector are taken from <a href="https://github.com/gleu/pgstats">pgstats</a> a C program writen by Guillaume Lelarge and especially the SQL queries including the compatibility with all PostgreSQL versions.</p>
	      <p>Btw $PROGRAM grapher is compatible with files generated by pgstats, sar and sadc so you can use it independently to graph those data. Some part of the sar output parser are taken from <a href="http://sysusage.darold.net/">SysUsage</a></p>
              </div>
              </div>
            </div><!--/span-->
	</div>
</li>
</ul> <!-- end of slides -->
EOF

}

sub show_sysinfo
{
	print <<EOF;
<ul id="slides">
<li class="slide active-slide" id="info-slide">

	<div id="info"><br/><br/><br/></div>
	<div class="row">
            <div class="col-md-4">
              <div class="panel panel-default">
              <div class="panel-heading">
              <i class="fa fa-desktop fa-2x pull-left fa-border"></i><h2>System</h2>
              </div>
              <div class="panel-body panel-xlheight">
		<div class="key-figures">
		<ul>
		<li></li>
	      <li><span class="figure">$sysinfo{KERNEL}{'hostname'}</span> <span class="figure-label">Hostname</span></li>
	      <li><span class="figure">$sysinfo{KERNEL}{'kernel'}</span> <span class="figure-label">Kernel</span></li>
	      <li><span class="figure">$sysinfo{KERNEL}{'arch'}</span> <span class="figure-label">Arch</span></li>
	      <li><span class="figure">$sysinfo{RELEASE}{'name'}</span> <span class="figure-label">Distribution</span></li>
EOF
		if ($sysinfo{RELEASE}{'version'}) {
			print <<EOF;
	      <li><span class="figure">$sysinfo{RELEASE}{'version'}</span> <span class="figure-label">Version</span></li>
EOF
		}
		print "<li>\n";
		foreach my $k (sort keys %{$sysinfo{SYSTEM}}) {
			next if ($k =~ /^kernel/);
			if ($k =~ /transparent_hugepage/) {
				my $k2 = $k;
				$k2 =~ s/\/sys\/kernel\/mm\//.../;
				$sysinfo{SYSTEM}{$k} =~ s/.*\[(.*)\].*/$1/;
				print <<EOF;
                <span class="figure-label" data-toggle="tooltip" data-placement="top" title="$k">$k2</span> <span class="figure">$sysinfo{SYSTEM}{$k}</span><br>
EOF
			} else {
				print <<EOF;
                <span class="figure-label">$k</span> <span class="figure">$sysinfo{SYSTEM}{$k}</span><br>
EOF
			}
		}
		print "</li>\n";
		my $core_info = '';
		if (exists $sysinfo{CPU}{'cpu cores'}) {
			my $nsockets = $sysinfo{CPU}{'processor'}/($sysinfo{CPU}{'cpu cores'}||1);
			$core_info = qq{
	      <li><span class="figure">$nsockets</span> <span class="figure-label">Sockets</span></li>
	      <li><span class="figure">$sysinfo{CPU}{'cpu cores'}</span> <span class="figure-label">Cores per CPU</span></li>
};
		}
		print <<EOF;
		</ul>
		</div>
              </div>
              </div>
            </div><!--/span-->
            <div class="col-md-4">
              <div class="panel panel-default">
              <div class="panel-heading">
              <i class="fa fa-tachometer fa-2x pull-left fa-border"></i><h2>CPU</h2>
              </div>
              <div class="panel-body panel-xlheight">
		<div class="key-figures">
		<ul>
		<li></li>
	      <li><span class="figure">$sysinfo{CPU}{'model name'}</span></li>
	      <li><span class="figure">$sysinfo{CPU}{'cpu MHz'}</span> <span class="figure-label">Speed</span></li>
	      <li><span class="figure">$sysinfo{CPU}{'cache size'}</span> <span class="figure-label">Cache</span></li>
	      $core_info
	      <li><span class="figure">$sysinfo{CPU}{'processor'}</span> <span class="figure-label">Cores</span></li>
		</ul>
		</div>
              </div>
              </div>
            </div><!--/span-->
            <div class="col-md-4">
              <div class="panel panel-default">
              <div class="panel-heading">
              <i class="fa fa-tasks fa-2x pull-left fa-border"></i><h2>Memory</h2>
              </div>
              <div class="panel-body panel-xlheight">
		<div class="key-figures">
		<ul>
		<li></li>
	      <li><span class="figure">$sysinfo{MEMORY}{'memtotal'}</span> <span class="figure-label">Total memory</span></li>
	      <li><span class="figure">$sysinfo{MEMORY}{'memfree'}</span> <span class="figure-label">Free memory</span></li>
	      <li><span class="figure">$sysinfo{MEMORY}{'buffers'}</span> <span class="figure-label">Buffers</span></li>
	      <li><span class="figure">$sysinfo{MEMORY}{'cached'}</span> <span class="figure-label">Cached</span></li>
	      <li><span class="figure">$sysinfo{MEMORY}{'swaptotal'}</span> <span class="figure-label">Total swap</span></li>
	      <li><span class="figure">$sysinfo{MEMORY}{'swapfree'}</span> <span class="figure-label">Free swap</span></li>
EOF
		if (exists $sysinfo{MEMORY}{'shmem'}) {
			print <<EOF;
	      <li><span class="figure">$sysinfo{MEMORY}{'shmem'}</span> <span class="figure-label">Shared memory</span></li>
EOF
		}
		if (exists $sysinfo{MEMORY}{'commitlimit'}) {
			print <<EOF;
	      <li><span class="figure">$sysinfo{MEMORY}{'commitlimit'}</span> <span class="figure-label">Commit limit</span></li>
	      <li><span class="figure">$sysinfo{MEMORY}{'committed_as'}</span> <span class="figure-label">Committed</span></li>
EOF
		}
		if (exists $sysinfo{SYSTEM}{'kernel.shmmax'} and exists $sysinfo{SYSTEM}{'kernel.shmall'}) {
		  $sysinfo{SYSTEM}{'kernel.shmmax'} = pretty_print_size($sysinfo{SYSTEM}{'kernel.shmmax'});
		  $sysinfo{SYSTEM}{'kernel.shmall'} = pretty_print_size($sysinfo{SYSTEM}{'kernel.shmall'} * 1024 * 4);
		  print <<EOF;
            <li><span class="figure">$sysinfo{SYSTEM}{'kernel.shmmax'}</span> <span class="figure-label">kernel.shmmax</span></li>
            <li><span class="figure">$sysinfo{SYSTEM}{'kernel.shmall'}</span> <span class="figure-label">kernel.shmall</span></li>
EOF
		}
		my @df_infos = ();
		push(@df_infos, @{$sysinfo{DF}}) if (exists $sysinfo{DF});
		my @mount_infos = ();
		push(@mount_infos, @{$sysinfo{MOUNT}}) if (exists $sysinfo{MOUNT});
		print <<EOF;
		</ul>
		</div>
              </div>
              </div>
            </div><!--/span-->
	</div>

	<div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
              <i class="fa fa-hdd-o fa-2x pull-left fa-border"></i><h2>Filesystem</h2>
              </div>
              <div class="panel-body panel-lheight">
		<div class="key-figures">
		<ul>
		<li></li>
		<li>
		<table>
		<tr><th>Filesystem</th><th>Size</th><th>Used</th><th>Free</th><th>Use%</th><th>Mount</th></tr>
		@df_infos
		</table>
		</li>
		<li>
		<table>
		<tr><th>Filesystem</th><th>Mount</th><th>type</th><th>Options</th></tr>
		@mount_infos
		</table>
		</li>
		</ul>
		</div>
              </div>
              </div>
            </div><!--/span-->
	</div>
EOF
		if (exists $sysinfo{PROCESS}) {
			print <<EOF;
	<div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
              <i class="fa fa-hdd-o fa-2x pull-left fa-border"></i><h2>Process list</h2>
              </div>
              <div class="panel-body panel-lheight">
		<div class="key-figures">
		<ul>
		<li></li>
		<li>
		<table>
		<tr><th>USER</th><th>PID</th><th>%CPU</th><th>%MEM</th><th>VSZ</th><th>RSS</th><th>TTY</th><th>STAT</th><th>START</th><th>TIME</th><th>COMMAND</th></tr>
		@{$sysinfo{PROCESS}}
		</table>
		</li>
		</ul>
		</div>
              </div>
              </div>
            </div><!--/span-->
	</div>

</li>
EOF
		}
	print <<EOF;
</ul> <!-- end of slides -->
EOF

}

sub html_header
{
	my @db_list = @_;

	my $pgcluu_ico =
        'data:image/png;base64,
iVBORw0KGgoAAAANSUhEUgAAACAAAAAjCAYAAAD17ghaAAAAAXNSR0IArs4c6QAAAAZiS0dEAP8A
/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB98GCwcGIvGIhhwAAAOBSURBVFjD
vZdZiI1hGMd/55gFM/Ylss4YGsuQLDP2C3uWGyVzI1mypOxSCAmFO2WJUJaoKReDIhcmSbYaaphG
msgWMXZmmPnc/L96ejvfd86ZOeOp03e+733e9/m/z/5EaBxFgWFAgd6fAg+BBv4D9QBuAj8BT79f
wG2gT3MK7gSs0y09PSt1+z8GzBagY6qFFwNvjZCfwEygNdAKmAJ8NOvvgOWpEFwAXDEH1wAngPQA
vzjsALlu/CQp6gKcBr6bwy4A+Qns7QucNPt+AGeBrokIjgArgM/mgCpgcpx9LbTX0ljgsTnnG7Aa
yAhTd7XZ8BfYKtW6NA7oad63yB9iAVsD1JpzXwDDXcZlhqEWOAfkhdx4krM+QsKCqJd8x4buGn+x
P/BVH8uBIQG3bipFBPqeMclwhMQDKgK82/fwZMIqO05SqpDM9VEgRx/vyO5B6N843yaHAM4HRoUA
KNczN2psVx+yoR4oNe9zgRvAfr2XKgf49AAoCTnP8520sbZeoudAmXA2sFL5I+mqlij1BLYBWUCd
STo9DE8bIA2Yn0oAUfnAUWA3sA+4q7VvwC3DWyNfuggcSAWAlsBi3Wy0bFcInAEuSyOl8odF8qfB
4lsBdIgHIC3Oegbw0omGzsobc8z3qXrmGAfLVP6vaYoGvqqi/XDU/gvoJjDdgXZae69MGgFeOeAb
7QPZ0tRSYK1ufkz9QTXwGngO7BXQkbL/GAGNS4ektmMxKlqGOp4nxlyzTEfkOb+DCTr/WfEfiaeB
PKCfwi1fTnXcJC3PPD2F34BU5oHnakrSJLxMNo8ap/TM/17A/URDMBEAtcAl4JNKboEERozwiDGd
J5/ZCCxIFoAXwLNR9b/I4fUMCM/RBMCEBGqBl6YOFpXPaIyiVCPvznHUHolhBktVIZf2a8YHgIkq
w3VqwVoEbLrmeP8LYDOwU+HmrzXIZO0DAGwAfmuWmOYe7insxscIyaEaRL6oNyg0azNMI9ugAcal
IuCRkVNm+4kosMss1mv8cm+RrvTaOiBki6VRV3tXnelpR1AZGKUhs84wrwLaNqJnyFaB8s+pUydU
GG9jujqeCrO5MsmecKGj7ipgngpUUrTTaaXLgUEh/Lmaku1UtKep7XRv4Lwzip9yzJIJHJFAn69E
gFJG04FnRsAnYDuwyRlIq9UjNgu1Uof0OkYlfKMuKCuZA/8B+QsSxkN8YYwAAAAASUVORK5CYII=
';
        my $date = localtime(time);
        print qq{Content-Type: text/html; charset=$charset

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Type" content="text/html; charset=$charset" />
    <meta name="robots" content="noindex,nofollow">
    <meta http-equiv="Expires" content="$date">
    <meta http-equiv="Generator" content="pgCluu v$VERSION">
    <meta http-equiv="Date" content="$date">

    <meta name="description" content="">
    <meta name="author" content="">
    <link rel="shortcut icon" href="$pgcluu_ico" />

    <title>$PROGRAM</title>
    <!-- Bootstrap core CSS -->
    <link href="$RSC_BASE/bootstrap.min.css" rel="stylesheet">
    <!-- FontAwesome CSS -->
    <link href="$RSC_BASE/font-awesome.min.css" rel="stylesheet">
    <!-- Custom styles for this template -->
    <link href="$RSC_BASE/pgcluu.css" rel="stylesheet">
    <!-- Datetime picker -->
    <link href="$RSC_BASE/datetimepicker.css" rel="stylesheet">
    <script src="$RSC_BASE/jquery.min.js"></script>
    <script src="$RSC_BASE/bootstrap.min.js"></script>
    <script src="$RSC_BASE/pgcluu.js"></script>
    <script src="$RSC_BASE/sorttable.js"></script>
    <script src="$RSC_BASE/bootstrap-datetimepicker.js"></script>
    <!-- HTML5 shim and Respond.js IE8 support of HTML5 elements and media queries -->
    <!--[if lt IE 9]>
      <script src="https://oss.maxcdn.com/libs/html5shiv/3.7.0/html5shiv.js"></script>
      <script src="https://oss.maxcdn.com/libs/respond.js/1.3.0/respond.min.js"></script>
    <![endif]-->
</head>

<body>

<!-- Load navbar -->
<div id="navigation">
};
	print &generate_menu();

	print qq{
</div>

<div class="container" id="main-container">
};

}

sub html_footer
{
	my $db = shift();

        print qq{
      <hr>

      <footer>
        <p>&copy; Gilles Darold 2012-2015</p>
	<p>Report generated by <a href="http://pgcluu.darold.net/">$PROGRAM</a> $VERSION.</p>
      </footer>

</div><!--/.container-->
</body>
</html>
};

}

sub generate_menu
{
        my $date = localtime(time);

	my $pgcluu_logo =
        'data:image/png;base64,
iVBORw0KGgoAAAANSUhEUgAAAJgAAAAsCAYAAACZmXFCAAAAAXNSR0IArs4c6QAAAAZiS0dEAP8A
/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB98GCwcUDSKty5YAABOVSURBVHja
7Vx7lF1Vff6+fe5MJi8SQh4ESIDI+2nrQtQCihVRsFhZKmh9oKII6rJSq6uCj7ZSLK0Wn0trVSit
BbUiRV0KUqlFRZRHKmCUdwpESEgCCTOTuXd/X/+Y3xl3DvfOI6Qugdlr3TV3zj1nn31++/t9v9fe
B3icTdLY95wzbI/9X36fbk/Nxm290DbI0cs7nQ5TSgO255BMtgdTSoMkc/Pc6TYNsHFbzhkAUFVV
DbQB288E8BIABwLoA3A/gO+QvILk+pLpUkrTUp9ukzaP+0g6V9L9kmzbxd9BSZfaPsL2QMl8NUin
23Tr6mvZXizpTZKuk+T4PCzp6pzztyXdXYBtnaQP296/V3/T7SncSke90+nMsv1Hki6TtMWjLdv+
L9tvyTkvzznvmHM+VtKFkjYWQLve9jsl7TYNtOkGSVuBK+d8hKTPSlpds5btm22fLWm/Lr7aTpJe
Y/u7trfENUOSLpd0kqS50yCbZi3YPjTn/PeSbpXUCaA8KOlvbR8uaaB5XQ0Y25C0wvZbJV1bmNP7
JH055/ySZvAw3Z46ftYM2++zfYukwdrU5Zz/RdIzcs6zukWY3djIdp+k3SW9W9LGYL+2pPttX5Rz
XlaCdJrRxp+bJxzz28bIyEgJlMNyzt+X1C5YZ42kE3POA+vXr0cDEP0551Q8+GLbe3e5Twpwfl9S
J0DbzjnfL+kU23yyM9p4yedev413ze+8nMoB5pwXSzrH9oMFsO6X9AlJyxvn1g+/QNIHcs77FwI5
Led8Qi9Nsz075/w2STcU9xm0/XVJz3gy+mZNkISFmC9poaQdmsrVBI7tubb/xPYrbL9S0sk55wOf
SBS8NOd8aTHhm2x/0fZh40247QFJz805L2ow2LwePl0J0mWS/tz26ohILelXpW/2RAZZ6YsWcjlZ
0vk5569I+o7tqyR9U9IXcs5nSjqw0+mMAazuI+d8YM55cyjikKTBnPP7nyiCmCHpvQW4rpP0opGR
kaoJjDCJrdIk9vLBymt6BQJxbE/bFxbR6bckrXgS+U9zbZ8i6ReScuHPupC5JWVJG3LO/yRpeUO2
B0naVJ+bcx6U9KHf+YcPUOwi6eoY/E9zzvuNE1XOkHRczvnQyTBMocUzbS+S1Net3+Hh4UrS50L4
d9h+8RMZVAUDLZb0sQJEGn3E3wCsBlzxWWf7pMYcHJRz3tRwKT74uy6HFLXBuQAWkATJH1ZVtao8
qVGorgDsAWDX6AA555mSDpE0rxDsnHa7PVZ7tP0020eTnNvsd8uWLRgYGMgkPx+F8R0ALCn9ku3h
90zF3HbxgaZ036qqkHNeAOBcAO8iaZKK30myTXKt7TW215DcWHSxBUD7ycDerZjQfgD9HpXi4ATX
DAG4CMBwcezVAM4A8Mmqqi7IOR9D8uiU0iUAVoZQ15AcArC52WF/fz8KwcN2C6NFcwJwr0mcaIVG
8/ca7OMV3ut+62J+r756sXVKCfEMle3TALxxtFs7noe2bwdwBYCfAHg0ju1K8tm2n0Vyju1qIhDX
Y6rvO56yBOAf81zN8QfJTPiME8m/Tje14qQxAdhOEzyUAWwqju1t+1Tbvw/gyJzzNQDOt70fyR0B
nA4AVVU9BOChbuCov5NkMIUnYpyYxD7bewJYYLsDoJVS2gTgFyQlaU/bB6eUFgYj3Gn7+pTScHNi
bG81LtsH2N7X9jySm0jeTnJlXLcryaW2FcPeYvvulNLmuk9J+6aU3lo8D+PzI5IfJPnDULhy8i4C
8CwAxwN4eDwGLeUXEz4gaS+Sc2OOKkmPAlhZVZVjDtDpdKqU0n4kF0rKJPtIrie5spBFZXt327uQ
7JBsBfH8D8lOLafAyh62l9nOJCuSm2zfQnILALQm0vpJmIkdAcyNGy4i+YdhQgngkJxzq6qqTn1y
u92eVP8kJ2PS5gN4u+0XxWT1214ZObWX234ryT0BzLItkg+RvErSuSml1QGEJrDm2H697dcBWE5y
BoAR22skXUbyfADPt312CL1l+z6SZwG4vp4kkscBWF6Ci+Q9ts9JKX2vZITapKaU1gP4tqQf92Lu
8bIAJM8GcCiADKAieSeAlwEYKcA4h+TbbR8bIJgB4Drbry5M+GwArwfw2njGftt3AzgJwIYCIzMB
vArAacHE/bZXkTwNwL1jAJuI7mqtLEzMcpLn2b5b0pUkB0OoO0WfbZIDkvpJJklH2T4FwOerqvrx
RAnFAOtk5NoPYHeSZVJ3Y0rp3bbfSXJhA7gLAOwNYHHO+fSqqh4sTYKkGQBOBfBhALNLmdheQnI/
AAfbvhXAPsU9F9ieU8irn+RR8SwOXzIDuILkf5dmq5ZpznnMvKaUNpRmpqqqCWUSbs4KAPsVc9qS
lBrnVQB2A7BnIes1je4qALuGctatL46XMqkALAGwrJDVcMwLxgBWD74XyIKCZ0rqD/NyakQ5q1NK
v7S9Lk59EMCVts8BkEj+AsBOJD8M4EgAS22fQfKu7bHK1aNOW6f4TgD7AjiwLqYXAHJ8EoATSd5o
+zySI4U5PtT2WSRn13m5WKFby2gAwEsBPAdAh2QrJr1TMg7JebafW1gEAtgY5nFTba62mtEuvtFU
5BNA7jRciC0pJTdlBiAXjI2QYTl+A8gNi7KlyapxbW6MtePiwq0YbALWOJLkzpK+TvL4OH8hgNkA
Pg7gHgCXpJR+Jek8APsD+EuS+9uuM86H2346gLu6Ca92Hqcg1LGxx3eF2STJywH8Rxx7QVB5LZCK
5Nts/1u73b6jr68PJGcCeAuAhbWASKbwOy60vc72gSTfE1pbYHBrxziy9LNioupjDwK4c7IBymQi
1YncmXAL2A20UwmSaj+yeX4vYir/34rBJqiTPUpyTTh2fXFufwj7SwD+MzQZJP8OQF+sGTs4Jgq2
ZwBYIqmVUupM9HCtVmvSICvGSZLfInkygKGIjL5Ocp3td0giSdneGcDxrVbrU6MEplkk31QDJ8Z8
h+3TSF4bzAcAK0n+awHCbmMqqxgplGeD7QemykyTcfK7BSm1MuWcNdVIsUyQF8rrbWHYVHZU+lld
fLAfkrwypdQheXXBuCoipZbt/vh/iKRSShtJDkX/QyTXbty4sdPL1ysfrtPpTFqTQ1PrvN5Hwy90
VVVOKW20fRnJB1JKiaMNkRaocs4k+bxamHEObF9M8oY4pqqqZPtySdeEC1BOQDmmHYuI23FshOTw
tjLWZNimOKcGv7pZiXK8PRRkDA8FS7lXXnE869fqQoVdTVen00FVVTMiHP0MgINsD5G8NqV0ku2D
AQwHS7UB3ATgKgA32b4EwPHBLNcsWLCga+5mWzS7FECkWX4N4K5mf3H8zmDc+roDAMwIs3l02U8k
O2+vfbTifiMAVgE4ohn1Ft/XFoxSp15mRnT222h1PjH3yntN5Hd3K/H1yiuO199joshuKA0k72D7
TyMv8jeSjk8ptaK6/w/xezmgDoDLAZy+du3ady1atOhTAO6NnFFPzZnqXsrSf4y/68okcBEBb7b9
SD3pRVQ5g+Sg7V1KVo8+HurhTNfrlXrNzmABeIWZXBjVj1t/i9v43GUly4SgaMyBez1nk9K6+tUT
TWyR13kOgLMBvM/2ISmloQiL32R7h7iZi0G1AJxg+4wlS5YgpXTHeODqBrbJbHEr+qqZog1AXbL3
3aKnqhZelHJKf4bsMtDa9ZogJzVI8sH6+jA5C0g+baIcX1miKs8pv3czyz3mvq/LbzPrXV5TYbBu
OdNIW8wajxTSFGz9orgJAfyBpHm23xshe23zWUdOYf9p+8RYxzS/rjtOdmHdZLW8Nm1x/sJIADbb
bADzYnJqv+iROglp++4Alovzl3TDNIDFRTjfDWAbAfygeB5HVeOYnPPS8Zz00qSVQGyY+27gcBdZ
zkgpseEvLSa5qARiD7m7YdX6euTeFtUy7TavaSIkF5pzW5SIqvAlTib5qlLQjURpnb0+yPanbH8k
57xiYGBgXICVTv5kV2s2tHkpyaVdtH4hgGWNybgrWFXhL47ly0hWtg9qt9sDjdvNBfDM8dikr68v
A/geAEU0Wv/4PAAn9grti4TvvpL2KFl8AjMG251wX8rzZ9TMU5SB9iS5x0SFAZK50dcs202QzcHo
ZuueLs5jTGQThsUD/hzAN8OBvhtAXWdTUWcr7XX9v4O9TiP5Ztsze5m+icLnSWT/60j2dNuprK1F
gnR55K7q+1xnuxPn/YzkMMlUMNPLqqp6Wb2qw/YSAGeT3L8oqzym8BzHryB5c2NsC0ieGdv3FnVR
5n1t/xnJjwN4+hS9+g0ANjUYaamkI4r+dyX5mvA93UvmkkZqP7P4fRHJo8tcH4C3RUXDPVh1zK6O
AaRbaBsXPhrrj3aJMsPTS0e3YDE3SiSO74nkQWHC/rdHIKFteWFK4bjXYH9lrLu6PEo0LwRwchEl
JtsZwLfjLwA8bPszAM4stHgZgHNsH297cyyMPGo8v7VQyHttnwvgy8FitVxXAPgAgBfbvt32WpKz
YvL3tH1opHiqqbgPJDfa3tBYlDCL5Eds/x6AIdvH2H5B03lvAqOqqmFJdxX+pqKi8X7be0naYPsI
kicUc97NZUUrEm/DUdQkyfndlmbEQ9xu+14AJzRMoRtrt1zetHiAobLw2pyU4hUDbQBD9SqAKWSb
STLbHghNPS7GMQ/AQPhpdTBwEYBba59H0paU0j8D+GMAK8JsKupxy+toMCb+HgBLo7jbjQFq/+kb
JN8ftc1UMPoCkscAOJpkO/rtDxmmWEnh8aK/bgnRMMvHhb/nGP8hAPYKRZob/XfCQWcv98j2qkjT
7FWDDMB+4Xd3ANRLilwr7XhO/gaMvrAEkQ86sqGNpT/EwndTwRojAB4AsL528GstCbOTSf6I5APd
IqNYw//ueNh1AO6bDMAagqftayNB2gKwmOTiGlwhUAK4y/bHY2nPqKa1WiB5K8m/AvBIsE4qos2+
WI7yjyQ/Ybu/nOyIUscUJpRz2Pb5GF1w2C5WVdTs0Re+zczyfrZbPVwVFlUXllFq/L3A9rWFOGrL
NCeUrEPysyS/V4MrPt2CvVtIfhe/oaYahbOiUlEB+DGAL9RF8BhHKqPsFBq80fZXo1C5v6QLJJ0Z
PkczZTAM4DuhZakA6ccAHEZyH9t/Wfdf+zwAfhQmayt2zDn3Szre9tdIvjR+vsH2zVM1lVEJaIVv
8FHbGyXVZoCRm7sOwBskreySkW5LuhijiwSvClO+FsB9US46JfpeXESHXet0tbxSSo/a/jSAY0he
HD7scCgDi0WWJvkAyWtIfgTA1Q0lzCQ3214LYC3JR8IibKVoKaXTbX8j/DEWlmW17Q+FeV4HYBPJ
eiXtI8Uusbqfh0l+jOSFgQ8WgdsaAJ8G8HLbd0bw9+uo1z4i6TdsVJjBWZHjOquuY9m+nuSnAXy1
XBwXC/2OCjqea/tG21+uqurhYtLeEuZhN9u32D61qqprG0ndw2y/B8Cx0Q9iIl9H8rZ2u42+vr7x
2GsXAJ+sI7ManABemFJ6KBzcZ2N0zVoGcBvJK0NAY0tmuq1wzTnPJ7l7mJXNsXJkvaSZAC4k+Ypi
lepK22+squqG8YrSOecZkQs7wPYyADuE9o+klO6XtArAr6qqWtfl2lkppWfGKgcGQO9OKd3TxaWZ
D+DZUZwfkPQAyetJ3hTPug/JBUEoLZKPpJRuLqsrBQHMA3A4yYNIzpa0NqV0Pcmf5pwTyWUxD4o0
1RBGF3yOjFm9Rgb+9bbvjR0u9YaEayQt7RKmYnBwsGstMf6fl3PePec8t5g4ttvt/tgIsanY8LAh
5/y5ctfRRAsObe9i+98bmyZ+2i1CGy+hWRamJc3OOfePw5IHSGrHPRUbN75oe8eJ2HUqTNxtD+pk
cofb+lbJ7b1z/DHjaABjhe0LbN8XW/ydcx6y/Q7byyS1xhtMt4HF6zXnS3qRpJ8XgNhg++pyF9FE
Kzt6ASzn7Jzzz8YD2HhCk7RzbDL+C9sHSlpie358lkg6XNKNoXg5zP8WSW+c7OSOd8723APa7Gtb
d4BvV+B1YaAX275E0v0555rNfmD7DbZ3v+KKKyY7cTtKOlbSlyRtKTb2ft/2GfXiwMkCqwSYpG1i
sB7jXBJv/3GE6ZdL+nx8vmv70fitU9zz4nrT8fQ7NSbZSrTb3iHnfHK8E2wohDos6XLbJ5emoeko
htCPtP0J2/cVIPiJpPfY3v3xaIWkXWxf2thTeMPjANjOti8rNgCP/a1bYy/jN+v9odNvB3qcbGZ7
qaR3BEOMbRCNF809t8v1KySdFbuZy9c2nWf7kO1BucFglzU2sd4kafE2PvM8SX8t6V5JIz02xW7O
Od8Ub21c8Xh9nyd742TYrCzA5pwPSSm90vabi3D9jog0vwZgg6TjUkonAXhO5FgE4GsAviTp6lar
Ndyr/ykCbJbt50e5YiTySr8GcGm9NW2yyhTRF20vsb0vgL1J7kZyVp1QBLCZ5C8lrZL0876+vk55
/XTbTk6jpBm2j7b9FdvDodlt26uCQcot7jdKeoPtnba3Q7t69eoaFMk22+0267zXVPvvdn6n0+mT
NNP2rJzzY4q9vd6HNt22U2QSrx56re2rbA+XvkqYxg9Kelqn00nbO1L6//J5JmPqpkG1HU3keCal
zh3ZXkrysHoJMkZXW1xH8rZyW9i0GZlu28QgnU4HtplzbknqyzmnRiQ6LbCnaPs/zGhC2bEgIrsA
AAAASUVORK5CYII=';

        my $menu_str = qq{
    <div class="navbar navbar-inverse navbar-fixed-top" role="navigation">
      <a class="navbar-brand" href="http://pgcluu.darold.net/">
      <img src="$pgcluu_logo" title="$PROGRAM"></a>
      <div class="container">
        <div class="navbar-header">
          <button type="button" class="navbar-toggle" data-toggle="collapse" data-target=".navbar-collapse">
            <span class="icon-bar"></span>
            <span class="icon-bar"></span>
            <span class="icon-bar"></span>
          </button>
        </div>
        <div class="navbar-collapse collapse">
          <ul class="nav navbar-nav">
              <li id="menu-home" class="dropdown"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=home&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Home</a></li>
              <li id="menu-info" class="dropdown"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=sysinfo&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">SysInfo</a></li>
};
	if ($#database_list >= 0) {

		$menu_str .= qq{
              <li id="menu-cluster" class="dropdown">
                <a href="#" class="dropdown-toggle" data-toggle="dropdown">Cluster <b class="caret"></b></a>
                <ul class="dropdown-menu">
		      <li id="menu-cluster-size"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-size&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Databases sizes</a></li>
		      <li id="menu-tablespace-size"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=tablespace-size&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Tablespaces sizes</a></li>
};
		$menu_str .= qq{
			<li id="menu-connectionbackend" class="dropdown-submenu">
			   <a href="#" tabindex="-1">Connections </a>
			      <ul class="dropdown-menu">
			      <li id="menu-cluster-backends"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-backends&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Connections</a></li>
			      <li id="menu-cluster-connections"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-connections&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Connections by type</a></li>
			      </ul>
			</li>
		      <li id="menu-cluster-deadlocks"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-deadlocks&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Deadlocks</a></li>
		      <li class="divider"></li>
		       <li id="menu-cluster-cache_ratio"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-cache_ratio&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Cache utilization</a></li>
			<li id="menu-pgbuffercache" class="dropdown-submenu">
			   <a href="#" tabindex="-1">Shared buffers statistics </a>
			      <ul class="dropdown-menu">
			      <li id="menu-cluster-buffersused"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-buffersused&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Shared buffers utilization</a></li>
			      <li id="menu-cluster-databaseloaded"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-databaseloaded&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Database in shared buffers</a></li>
			      <li id="menu-cluster-usagecount"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-usagecount&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Usagecount in shared buffers</a></li>
			      <li id="menu-cluster-isdirty"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-isdirty&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Usagecount in dirty buffers</a></li>
			      </ul>
			</li>
		      <li class="divider"></li>
			<li id="menu-backgroundwriter" class="dropdown-submenu">
			   <a href="#" tabindex="-1">Background writer </a>
			      <ul class="dropdown-menu">
			      <li id="menu-cluster-bgwriter"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-bgwriter&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Background writer buffers</a></li>
			      <li id="menu-cluster-bgwriter_count"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-bgwriter_count&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Background writer counters</a></li>
			      </ul>
		        </li>
			<li id="menu-temporaryfiles" class="dropdown-submenu">
			   <a href="#" tabindex="-1">Temporary files </a>
			      <ul class="dropdown-menu">
			      <li id="menu-cluster-temporary_files"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-temporary_files&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Temporary files</a></li>
			      <li id="menu-cluster-temporary_bytes"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-temporary_bytes&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Temporary files size</a></li>
			      </ul>
		        </li>
			<li id="menu-walcheckpoint" class="dropdown-submenu">
			   <a href="#" tabindex="-1">Wal / Checkpoint </a>
			      <ul class="dropdown-menu">
			      <li id="menu-cluster-xlog_files"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-xlog_files&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Wal files</a></li>
			      <li id="menu-cluster-xlog"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-xlog&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Wal bytes written</a></li>
			      <li id="menu-cluster-checkpoints"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-checkpoints&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Checkpoints counter</a></li>
			      <li id="menu-cluster-checkpoints_time"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-checkpoints_time&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Checkpoints write time</a></li>
			      <li id="menu-cluster-archive"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-archive&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Archiver stats</a></li>
			      </ul>
		        </li>
			<li id="menu-rw" class="dropdown-submenu">
			   <a href="#" tabindex="-1">Queries Reads / Writes </a>
			      <ul class="dropdown-menu">
			      <li id="menu-cluster-read_ratio"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-read_ratio&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Read tuples</a></li>
			      <li id="menu-cluster-write_ratio"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-write_ratio&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Write ratio</a></li>
			      <li id="menu-cluster-read_write_query"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-read_write_query&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Read vs Write queries</a></li>
			      <li id="menu-cluster-commits_rollbacks"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-commits_rollbacks&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Commits vs Rollbacks</a></li>
			      </ul>
		        </li>
		      <li class="divider"></li>
			<li id="menu-replication" class="dropdown-submenu">
			   <a href="#" tabindex="-1">Replication statistics </a>
			      <ul class="dropdown-menu">
			      <li id="menu-cluster-replication"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-replication&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Replication lag</a></li>
			      <li id="menu-cluster-canceled_queries"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-canceled_queries&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Canceled queries</a></li>
			      <li id="menu-cluster-conflicts"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-conflicts&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Conflicts</a></li>
			      </ul>
		        </li>
};
		$menu_str .= qq{
		      <li class="divider"></li>
			<li id="menu-configuration" class="dropdown-submenu">
			   <a href="#" tabindex="-1">Configurations </a>
			      <ul class="dropdown-menu">
			      <li id="menu-cluster-pgconf"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-pgconf&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">PostgreSQL configuration</a></li>
			      <li id="menu-cluster-settings"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-settings&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">PostgreSQL settings</a></li>
			      <li id="menu-cluster-dbrolesetting"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-dbrolesetting&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Database/Roles settings</a></li>
			      <li id="menu-cluster-alterconf"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-alterconf&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">PostgreSQL ALTER SYSTEM configuration</a></li>
			      <li id="menu-cluster-recoveryconf"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-recoveryconf&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">PostgreSQL recovery configuration</a></li>
			      <li id="menu-cluster-pghba"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-pghba&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">PostgreSQL authorization</a></li>
			      <li id="menu-cluster-pgident"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-pgident&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">User Name Maps</a></li>
			      <li id="menu-cluster-pgbouncer"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=all&action=cluster-pgbouncer&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Pgbouncer settings</a></li>
			     </ul>
			</li>
                </ul>
              </li>
};
	}

	if ($#database_list >= 0) {
		$menu_str .= qq{
              <li id="menu-database" class="dropdown">
                <a href="#" class="dropdown-toggle" data-toggle="dropdown">Databases <b class="caret"></b></a>
                <ul class="dropdown-menu">
};
	}

	foreach my $db (sort @database_list) {
		next if (($db eq 'all') || (($#INCLUDE_DB >= 0) && (!grep($db =~ /^$_$/, @INCLUDE_DB))));
		$menu_str .= qq{
		<li id="menu-$db" class="dropdown-submenu">
		   <a href="#" tabindex="-1">$db </a>
		      <ul class="dropdown-menu">
		      <li id="menu-database-info"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-info&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Database info</a></li>
};

		my %data_info = %{$DB_GRAPH_INFOS{'pg_stat_all_tables.csv'}};
		my $table_str = '';
		foreach my $id (sort {$a <=> $b} keys %data_info) {
			next if ($data_info{$id}{name} !~ /^table-/);
			$table_str .= qq{
			      <li id="menu-$data_info{$id}{name}"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=$data_info{$id}{name}&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">$data_info{$id}{menu}</a></li>
};
		}
		%data_info = %{$DB_GRAPH_INFOS{'pg_class_size.csv'}};
		foreach my $id (sort {$a <=> $b} keys %data_info) {
			next if ($data_info{$id}{name} !~ /^table-/);
			$table_str .= qq{
			      <li id="menu-$data_info{$id}{name}"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=$data_info{$id}{name}&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">$data_info{$id}{menu}</a></li>
};
		}
		%data_info = %{$DB_GRAPH_INFOS{'pg_statio_all_tables.csv'}};
		foreach my $id (sort {$a <=> $b} keys %data_info) {
			next if ($data_info{$id}{name} !~ /^statio-/);
			$table_str .= qq{
			      <li id="menu-$data_info{$id}{name}"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=$data_info{$id}{name}&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">$data_info{$id}{menu}</a></li>
};
		}
		my $disable_table = ' disabled';
		$disable_table = '' if ($table_str);
		$menu_str .= qq{
			<li id="menu-$db-table" class="dropdown-submenu $disable_table">
			   <a href="#" tabindex="-1">Tables statistics </a>
			      <ul class="dropdown-menu">
				$table_str
			  </ul>
		      </li>
};
		$table_str = '';

		my $idx_str = '';
		%data_info = %{$DB_GRAPH_INFOS{'pg_stat_all_indexes.csv'}};
		foreach my $id (sort {$a <=> $b} keys %data_info) {
			next if ($data_info{$id}{name} !~ /^index-/);
			$idx_str .= qq{
			      <li id="menu-$data_info{$id}{name}"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=$data_info{$id}{name}&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">$data_info{$id}{menu}</a></li>
};
		}
		%data_info = %{$DB_GRAPH_INFOS{'pg_class_size.csv'}};
		foreach my $id (sort {$a <=> $b} keys %data_info) {
			next if ($data_info{$id}{name} !~ /^index-/);
			$idx_str .= qq{
			      <li id="menu-$data_info{$id}{name}"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=$data_info{$id}{name}&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">$data_info{$id}{menu}</a></li>
};
		}
		%data_info = %{$DB_GRAPH_INFOS{'pg_statio_all_indexes.csv'}};
		foreach my $id (sort {$a <=> $b} keys %data_info) {
			next if ($data_info{$id}{name} !~ /^statio-/);
			$idx_str .= qq{
				      <li id="menu-$data_info{$id}{name}"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=$data_info{$id}{name}&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">$data_info{$id}{menu}</a></li>
	};
		}
		%data_info = %{$DB_GRAPH_INFOS{'pg_stat_unused_indexes.csv'}};
		foreach my $id (sort {$a <=> $b} keys %data_info) {
			$idx_str .= qq{
			      <li id="menu-$data_info{$id}{name}"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=$data_info{$id}{name}&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">$data_info{$id}{menu}</a></li>
};
		}
		%data_info = %{$DB_GRAPH_INFOS{'pg_stat_redundant_indexes.csv'}};
		foreach my $id (sort {$a <=> $b} keys %data_info) {
			$idx_str .= qq{
			      <li id="menu-$data_info{$id}{name}"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=$data_info{$id}{name}&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">$data_info{$id}{menu}</a></li>
};
		}
		%data_info = %{$DB_GRAPH_INFOS{'pg_stat_missing_fkindexes.csv'}};
		foreach my $id (sort {$a <=> $b} keys %data_info) {
			$idx_str .= qq{
			      <li id="menu-$data_info{$id}{name}"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=$data_info{$id}{name}&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">$data_info{$id}{menu}</a></li>
};
		}
		my $disable_idx = ' disabled';
		$disable_idx = '' if ($idx_str);
		$menu_str .= qq{
			<li id="menu-$db-table" class="dropdown-submenu $disable_idx">
			   <a href="#" tabindex="-1">Indexes statistics </a>
				<ul class="dropdown-menu">
				$idx_str
				</ul>
			</li>
			<li id="menu-database-functions"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-functions&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Functions statistics</a></li>
};

		%data_info = %{$DB_GRAPH_INFOS{'pg_relation_buffercache.csv'}};
		my $buffer_str = '';
		foreach my $id (sort {$a <=> $b} keys %data_info) {
			next if ($data_info{$id}{name} !~ /buffercache/);
			$buffer_str .= qq{
			      <li id="menu-$data_info{$id}{name}"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=$data_info{$id}{name}&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">$data_info{$id}{menu}</a></li>
};
		}
		my $disable_buffer = ' disabled';
		$disable_buffer = '' if ($buffer_str);
		$menu_str .= qq{
			<li id="menu-$db-buffercache-relation" class="dropdown-submenu $disable_buffer">
			   <a href="#" tabindex="-1">Buffercache Statistics </a>
			      <ul class="dropdown-menu">
				$buffer_str
			  </ul>
		      </li>
};
		$buffer_str = '';

		$menu_str .= qq{
		      <li id="menu-database-queries"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-queries&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Statements statistics</a></li>
};

		$menu_str .= qq{
		      <li class="divider"></li>
		      <li id="menu-database-size"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-size&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Database size</a></li>
		      <li id="menu-${db}_connections" class="dropdown-submenu">
			<a href="#" tabindex="-1">Connections </a>
			  <ul class="dropdown-menu">
			      <li id="menu-database-backends"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-backends&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Connections</a></li>
			      <li id="menu-database-connections"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-connections&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Connections by type</a></li>
			  </ul>
		      </li>
		      <li id="menu-database-cache_ratio"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-cache_ratio&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Cache utilization</a></li>
		      <li class="divider"></li>
		      <li id="menu-${db}_locks" class="dropdown-submenu">
			<a href="#" tabindex="-1">Locks </a>
			  <ul class="dropdown-menu">
			      <li id="menu-database-deadlocks"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-deadlocks&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Deadlocks</a></li>
			      <li id="menu-database-lock-types"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-lock-types&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Locks per types</a></li>
			      <li id="menu-database-lock-modes"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-lock-modes&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Locks per modes</a></li>
			      <li id="menu-database-lock-granted"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-lock-granted&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Locks granted or not</a></li>
			  </ul>
		      </li>
		      <li class="divider"></li>
		      <li id="menu-${db}_temporaryfiles" class="dropdown-submenu">
			<a href="#" tabindex="-1">Temporary files </a>
			  <ul class="dropdown-menu">
			      <li id="menu-database-temporary_files"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-temporary_files&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Temporary files</a></li>
			      <li id="menu-database-temporary_bytes"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-temporary_bytes&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Temporary files size</a></li>
			  </ul>
		      </li>
		      <li id="menu-${db}_rw" class="dropdown-submenu">
			<a href="#" tabindex="-1">Queries Reads / Writes </a>
			  <ul class="dropdown-menu">
			      <li id="menu-database-read_ratio"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-read_ratio&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Read tuples</a></li>
			      <li id="menu-database-write_ratio"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-write_ratio&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Write ratio</a></li>
			      <li id="menu-database-read_write_query"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-read_write_query&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Read vs Write queries</a></li>
			      <li id="menu-database-commits_rollbacks"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-commits_rollbacks&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Commits vs Rollbacks</a></li>
			  </ul>
		      </li>
		      <li class="divider"></li>
		      <li id="menu-database-canceled_queries"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-canceled_queries&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Canceled queries</a></li>
		      <li id="menu-database-conflicts"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=database-conflicts&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Conflicts</a></li>
                      </ul>
                </li>
};
	}
	if ($#database_list >= 0) {
		$menu_str .= qq{
                </ul>
              </li>
};
	}

	my @pgbouncer_list = ();
	if ($#pgbouncer_list >= 0) {
		$menu_str .= qq{
              <li id="menu-database" class="dropdown">
                <a href="#" class="dropdown-toggle" data-toggle="dropdown">pgBouncer <b class="caret"></b></a>
                <ul class="dropdown-menu">
};
		foreach my $db (sort @pgbouncer_list) {
			$menu_str .= qq{
			<li id="menu-$db" class="dropdown-submenu">
			   <a href="#" tabindex="-1">$db </a>
			      <ul class="dropdown-menu">
			      <li id="menu-pgbouncer-connections"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=pgbouncer-connections&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Clients / servers connections</a></li>
			      <li id="menu-pgbouncer-duration"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=pgbouncer-duration&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Average queries duration</a></li>
			      <li id="menu-pgbouncer-number"><a href="" onclick="document.location.href='$SCRIPT_NAME?db=$db&action=pgbouncer-number&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Queries per second</a></li>
                             </ul>
                        </li>
};
		}
		$menu_str .= qq{
                </ul>
              </li>
};
	}

	if (!$DISABLE_SAR) {
		$menu_str .= qq{
              <li id="menu-system" class="dropdown">
                <a href="#" class="dropdown-toggle" data-toggle="dropdown">System <b class="caret"></b></a>
                <ul class="dropdown-menu">
		  <li id="menu-system-cpu"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=system-cpu&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Cpu</a></li>
                  <li class="divider"></li>
                  <li id="menu-system-memory"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=system-memory&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Memory</a></li>
                  <li id="menu-system-swap"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=system-swap&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Swap</a></li>
                  <li class="divider"></li>
                  <li id="menu-system-load"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=system-load&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Load</a></li>
                  <li id="menu-system-process"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=system-process&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Task list</a></li>
                  <li id="menu-system-runqueue"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=system-runqueue&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Run queue</a></li>
                  <li id="menu-system-cswch"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=system-cswch&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Context switches</a></li>
                  <li id="menu-system-pcrea"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=system-pcrea&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Tasks created per second</a></li>
                  <li class="divider"></li>
                  <li id="menu-system-block"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=system-block&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Blocks</a></li>
                  <li id="menu-system-tps"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=system-tps&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Transfers per second</a></li>
                  <li id="menu-system-page"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=system-page&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Pages</a></li>
                  <li class="divider"></li>
};
		my $idx = 0;
		for (my $i = 0; $i <= $#DEVICE_LIST; $i++) {
			next if (!&device_in_report($DEVICE_LIST[$i]));
			my $md = $i % 10;
			if ($md == 0) {
				$idx++;
				if ($i > 0) {
					$menu_str .= qq{
		    </ul>
		  </li>
};
				}
				my $lbl = '';
				$lbl = " (part $idx)" if ($#DEVICE_LIST >= 10);
				$menu_str .= qq{
		  <li id="menu-device$idx" class="dropdown-submenu">
		     <a href="#" tabindex="-1">Devices $lbl</a>
		      <ul class="dropdown-menu">
};
			}
			$menu_str .= qq{
			  <li id="menu-device$i" class="dropdown-submenu">
			     <a href="#" tabindex="-1">$DEVICE_LIST[$i] </a>
			      <ul class="dropdown-menu">
			      <li id="menu-system-cpudevice"><a href="" onclick="document.location.href='$SCRIPT_NAME?dev=$DEVICE_LIST[$i]&action=system-cpudevice&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Cpu utilization</a></li>
			      <li id="menu-system-rwdevice"><a href="" onclick="document.location.href='$SCRIPT_NAME?dev=$DEVICE_LIST[$i]&action=system-rwdevice&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Read/write bytes per second</a></li>
			      <li id="menu-system-tpsdevice"><a href="" onclick="document.location.href='$SCRIPT_NAME?dev=$DEVICE_LIST[$i]&action=system-tpsdevice&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Transfert per second</a></li>
			      <li id="menu-system-srvtime"><a href="" onclick="document.location.href='$SCRIPT_NAME?dev=$DEVICE_LIST[$i]&action=system-srvtime&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Average service time</a></li>
			      </ul>
			  </li>
};
		}
		if ($#IFACE_LIST >= 0) {
			$menu_str .= qq{
		    </ul>
		  </li>
		  <li id="menu-network" class="dropdown-submenu">
		     <a href="#" tabindex="-1">Network </a>
		      <ul class="dropdown-menu">
};
			for (my $i = 0; $i <= $#IFACE_LIST; $i++) {
				next if (!&interface_in_report($IFACE_LIST[$i]));
				$menu_str .= qq{
			  <li id="menu-device$i" class="dropdown-submenu">
			     <a href="#" tabindex="-1">$IFACE_LIST[$i] </a>
			      <ul class="dropdown-menu">
			      <li id="menu-network-utilization"><a href="" onclick="document.location.href='$SCRIPT_NAME?dev=$IFACE_LIST[$i]&action=network-utilization&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Network utilization</a></li>
			      <li id="menu-network-error"><a href="" onclick="document.location.href='$SCRIPT_NAME?dev=$IFACE_LIST[$i]&action=network-error&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">Network errors</a></li>
			      </ul>
			  </li>
};
			}
			$menu_str .= qq{
		    </ul>
		  </li>
};
		}
		$menu_str .= qq{
                </ul>
              </li>
};
	}
	my $begin_date = '';
        $begin_date = "$o_year-$o_month-$o_day $o_hour:00" if ($o_year);
	my $end_date = '';
        $end_date = "$e_year-$e_month-$e_day $e_hour:59" if ($e_year);

	$menu_str .= qq{
              <li id="menu-about" class="dropdown"><a href="" onclick="document.location.href='$SCRIPT_NAME?action=about&end='+document.getElementById('end-date').value+'&start='+document.getElementById('start-date').value; return false;">About</a></li>
              <li id="menu-enddate"class="pull-right"><br><br><span style="color: white;">End date:</span> <input size="16" type="text" value="$end_date" id="end-date" readonly class="form_datetime"></li>
              <li id="menu-startdate" class="pull-right"><br><br><span style="color: white;">Start date:</span> <input size="16" type="text" value="$begin_date" id="start-date" readonly class="form_datetime"></div></li>
          </ul>
        </div><!--/.nav-collapse -->
      </div>
    </div>
<script type="text/javascript">
    \$(".form_datetime").datetimepicker({
        format: "yyyy-mm-dd hh:ii",
        autoclose: true,
        todayBtn: true,
        pickerPosition: "bottom-left"
    });
</script>            

};

	return $menu_str;
}

sub device_in_report
{
	my $device = shift;

	return 1 if ($#INCLUDE_DEV == -1);

	foreach my $g (@INCLUDE_DEV) {
		return 1 if (grep(/^$g$/, $device));
	}
	return 0;
}

sub interface_in_report
{
	my $device = shift;

	return 1 if ($#INCLUDE_IFACE == -1);

	foreach my $g (@INCLUDE_IFACE) {
		return 1 if (grep(/^$g$/, $device));
	}
	return 0;
}

sub compute_cpu_stat
{
	my %ncpu = ();
	for (my $i = 0; $i <= $#_; $i++) {
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);
		# hostname;interval;timestamp;CPU;%user;%nice;%system;%iowait;%steal;%idle
		# hostname;interval;timestamp;CPU;%usr;%nice;%sys;%iowait;%steal;%irq;%soft;%guest;%idle

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));

		map { s/,/\./ } @data ;
		# we only store all cpu statistics
		if ($data[3] eq 'all') {
			my $total_cpu = ($data[6]||0) + ($data[4]||0);
			if ($ACTION ne 'home') {
				$sar_cpu_stat{$data[2]}{$data[3]}{total}  = $total_cpu;
				$sar_cpu_stat{$data[2]}{$data[3]}{system} = ($data[6]||0);
				$sar_cpu_stat{$data[2]}{$data[3]}{user}   = ($data[4]||0);
				$sar_cpu_stat{$data[2]}{$data[3]}{iowait} = ($data[7]||0);
				$sar_cpu_stat{$data[2]}{$data[3]}{idle}   = ($data[-1]||0);
			}
			if (!exists $OVERALL_STATS{'system'}{'cpu'} || ($OVERALL_STATS{'system'}{'cpu'}[1] < $total_cpu)) {
				@{$OVERALL_STATS{'system'}{'cpu'}} = ($data[2], $total_cpu);
			}
			$OVERALL_STATS{'sar_start_date'} = $data[2] if (!$OVERALL_STATS{'sar_start_date'} || ($OVERALL_STATS{'sar_start_date'} gt $data[2]));
			$OVERALL_STATS{'sar_end_date'} = $data[2] if (!$OVERALL_STATS{'sar_end_date'} || ($OVERALL_STATS{'sar_end_date'} lt $data[2]));
		} else {
			$ncpu{$data[3]} = '';
		}
	}
	$OVERALL_STATS{'system'}{'ncpu'} = (scalar keys %ncpu);
}

sub compute_cpu_report
{
	my $data_info = shift();

	my %cpu_stat = ();
	foreach my $t (sort {$a <=> $b} keys %sar_cpu_stat) {
		foreach my $cpu (keys %{$sar_cpu_stat{$t}}) {
			
			if ($cpu eq 'all') {
				$cpu_stat{$cpu}{total}  .= '[' . $t . ',' . $sar_cpu_stat{$t}{$cpu}{total} . '],';
				$cpu_stat{$cpu}{system} .= '[' . $t . ',' . $sar_cpu_stat{$t}{$cpu}{system} . '],';
				$cpu_stat{$cpu}{user}   .= '[' . $t . ',' . $sar_cpu_stat{$t}{$cpu}{user} . '],';
				$cpu_stat{$cpu}{iowait} .= '[' . $t . ',' . $sar_cpu_stat{$t}{$cpu}{iowait} . '],';
				$cpu_stat{$cpu}{idle}   .= '[' . $t . ',' . $sar_cpu_stat{$t}{$cpu}{idle} . '],';
			}
		}
	}
	%sar_cpu_stat = ();
  
	if (scalar keys %cpu_stat > 0) {
		$cpu_stat{'all'}{total} =~ s/,$//;
		$cpu_stat{'all'}{system} =~ s/,$//;
		$cpu_stat{'all'}{user} =~ s/,$//;
		$cpu_stat{'all'}{iowait} =~ s/,$//;
		$cpu_stat{'all'}{idle} =~ s/,$//;

		print &flotr2_linegraph_array($IDX++, 'system-cpu', $data_info, 'all', $cpu_stat{'all'}{total}, $cpu_stat{'all'}{system}, $cpu_stat{'all'}{user}, $cpu_stat{'all'}{iowait});
	}

}

sub compute_load_stat
{
	for (my $i = 0; $i <= $#_; $i++) {
		# hostname;interval;timestamp;runq-sz;plist-sz;ldavg-1;ldavg-5;ldavg-15
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));

		map { s/,/\./ } @data ;
		$data[5] ||= 0;
		if ($ACTION ne 'home') {
			$sar_load_stat{$data[2]}{'ldavg-1'}  = $data[5];
			$sar_load_stat{$data[2]}{'ldavg-5'}  = ($data[6]||0);
			$sar_load_stat{$data[2]}{'ldavg-15'} = ($data[7]||0);
		} else {
			if (!exists $OVERALL_STATS{'system'}{'load'} || ($OVERALL_STATS{'system'}{'load'}[1] < $data[5])) {
				@{$OVERALL_STATS{'system'}{'load'}} = ($data[2], $data[5]);
			}
		}
	}
}

sub compute_load_report
{
	my $data_info = shift();

	my %load_stat = ();
	foreach my $t (sort { $a <=> $b } keys %sar_load_stat) {
		$load_stat{'ldavg-1'}  .= '[' . $t . ',' . $sar_load_stat{$t}{'ldavg-1'} . '],';
		$load_stat{'ldavg-5'}  .= '[' . $t . ',' . $sar_load_stat{$t}{'ldavg-5'} . '],';
		$load_stat{'ldavg-15'} .= '[' . $t . ',' . $sar_load_stat{$t}{'ldavg-15'} . '],';
	}
	%sar_load_stat = ();

	if (scalar keys %load_stat > 0) {
		$load_stat{'ldavg-1'} =~ s/,$//;
		$load_stat{'ldavg-5'} =~ s/,$//;
		$load_stat{'ldavg-15'} =~ s/,$//;
		print &flotr2_linegraph_array($IDX++, 'system-load', $data_info, '', $load_stat{'ldavg-1'}, $load_stat{'ldavg-5'}, $load_stat{'ldavg-15'});
	}
}

sub compute_process_stat
{

	for (my $i = 0; $i <= $#_; $i++) {
		# hostname;interval;timestamp;runq-sz;plist-sz;ldavg-1;ldavg-5;ldavg-15
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));

		map { s/,/\./ } @data ;
		$data[4] ||= 0;
		if ($ACTION ne 'home') {
			$sar_process_stat{$data[2]}{'plist-sz'} = $data[4];
			$sar_process_stat{$data[2]}{'runq-sz'} .= ($data[3]||0);
		} else {
			if (!exists $OVERALL_STATS{'system'}{'process'} || ($OVERALL_STATS{'system'}{'process'}[1] < $data[4])) {
				@{$OVERALL_STATS{'system'}{'process'}} = ($data[2], $data[4]);
			}
		}
	}
}

sub compute_process_report
{
	my $data_info = shift();

	my %process_stat = ();
	foreach my $t (sort {$a <=> $b} keys %sar_process_stat) {
		$process_stat{'plist-sz'} .= '[' . $t . ',' . $sar_process_stat{$t}{'plist-sz'} . '],' if (exists $sar_process_stat{$t}{'plist-sz'});
		$process_stat{'runq-sz'}  .= '[' . $t . ',' . $sar_process_stat{$t}{'runq-sz'} . '],' if (exists $sar_process_stat{$t}{'runq-sz'});
	}
	if (scalar keys %process_stat > 0) {
		if ($data_info->{name} eq 'system-process') {
			$process_stat{'plist-sz'} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'system-process', $data_info, '', $process_stat{'plist-sz'});
		} elsif ($data_info->{name} eq 'system-runqueue') {
			$process_stat{'runq-sz'} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'system-runqueue', $data_info, '', $process_stat{'runq-sz'});
		}
	}
}

sub compute_context_stat
{

	for (my $i = 0; $i <= $#_; $i++) {
		# hostname;interval;timestamp;proc;cswch
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));

		map { s/,/\./ } @data ;
		$data[4] ||= 0;
		if ($ACTION ne 'home') {
			$sar_context_stat{$data[2]}{'cswch'}  = $data[4];
			$sar_context_stat{$data[2]}{'pcrea'}  = ($data[3]||0);
		} else {
			if (!exists $OVERALL_STATS{'system'}{'cswch'} || ($OVERALL_STATS{'system'}{'cswch'}[1] < $data[4])) {
				@{$OVERALL_STATS{'system'}{'cswch'}} = ($data[2], $data[4]);
			}
		}
	}
}

sub compute_context_report
{
	my $data_info = shift();

	my %context_stat = ();
	foreach my $t (sort {$a <=> $b} keys %sar_context_stat) {
		if ($data_info->{name} eq 'system-cswch') {
			$context_stat{'cswch'}  .= '[' . $t . ',' . $sar_context_stat{$t}{'cswch'} . '],';
		} elsif ($data_info->{name} eq 'system-pcrea') {
			$context_stat{'pcrea'}   .= '[' . $t . ',' . $sar_context_stat{$t}{'pcrea'} . '],';
		}
	}
	if (scalar keys %context_stat > 0) {
		if ($data_info->{name} eq 'system-cswch') {
			$context_stat{'cswch'} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'system-cswch', $data_info, '', $context_stat{'cswch'});
		} elsif ($data_info->{name} eq 'system-pcrea') {
			$context_stat{'pcrea'} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'system-pcrea', $data_info, '', $context_stat{'pcrea'});
		}
	}
}

sub compute_memory_stat
{
	for (my $i = 0; $i <= $#_; $i++) {
		# hostname;interval;timestamp;kbmemfree;kbmemused;%memused;kbbuffers;kbcached;kbcommit;%commit
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));

		map { s/,/\./ } @data ;
		my $kbcached = ($data[7]*1024) || 0;
		if ($ACTION ne 'home') {
			$sar_memory_stat{$data[2]}{'kbcached'}  = $kbcached;
			$sar_memory_stat{$data[2]}{'kbbuffers'} = ($data[6]*1024)||0;
			$sar_memory_stat{$data[2]}{'kbmemfree'} = ($data[3]*1024)||0;
		} else {
			if (!exists $OVERALL_STATS{'system'}{'kbcached'} || ($OVERALL_STATS{'system'}{'kbcached'}[1] > $kbcached)) {
				@{$OVERALL_STATS{'system'}{'kbcached'}} = ($data[2], $kbcached);
			}
		}
	}
}

sub compute_memory_report
{
	my $data_info = shift();

	my %memory_stat = ();
	foreach my $t (sort {$a <=> $b} keys %sar_memory_stat) {
		$memory_stat{'kbcached'}  .= '[' . $t . ',' . $sar_memory_stat{$t}{'kbcached'} . '],';
		$memory_stat{'kbbuffers'} .= '[' . $t . ',' . $sar_memory_stat{$t}{'kbbuffers'} . '],';
		$memory_stat{'kbmemfree'} .= '[' . $t . ',' . $sar_memory_stat{$t}{'kbmemfree'} . '],';
	}
	%sar_memory_stat = ();
	if (scalar keys %memory_stat > 0) {
		$memory_stat{'kbcached'} =~ s/,$//;
		$memory_stat{'kbbuffers'} =~ s/,$//;
		$memory_stat{'kbmemfree'} =~ s/,$//;
		print &flotr2_linegraph_array($IDX++, 'system-memory', $data_info, '', $memory_stat{'kbcached'}, $memory_stat{'kbbuffers'}, $memory_stat{'kbmemfree'});
	}
}

sub compute_swap_stat
{
	for (my $i = 0; $i <= $#_; $i++) {
		# hostname;interval;timestamp;pswpin/s;pswpout/s
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));

		map { s/,/\./ } @data ;
		$data[3] ||= 0;
		$data[4] ||= 0;
		if ($ACTION ne 'home') {
			$sar_swap_stat{$data[2]}{'pswpin/s'}  = $data[3];
			$sar_swap_stat{$data[2]}{'pswpout/s'} = $data[4];
		} else {
			if (!exists $OVERALL_STATS{'system'}{'pswpin'} || ($OVERALL_STATS{'system'}{'pswpin'}[1] < $data[3])) {
				@{$OVERALL_STATS{'system'}{'pswpin'}} = ($data[2], $data[3]);
			}
			if (!exists $OVERALL_STATS{'system'}{'pswpout'} || ($OVERALL_STATS{'system'}{'pswpout'}[1] < $data[4])) {
				@{$OVERALL_STATS{'system'}{'pswpout'}} = ($data[2], $data[4]);
			}
		}
	}
}

sub compute_swap_report
{
	my $data_info = shift();

	my %swap_stat = ();
	foreach my $t (sort {$a <=> $b} keys %sar_swap_stat) {
		$swap_stat{'pswpin/s'}  .= '[' . $t . ',' . $sar_swap_stat{$t}{'pswpin/s'} . '],';
		$swap_stat{'pswpout/s'} .= '[' . $t . ',' . $sar_swap_stat{$t}{'pswpout/s'} . '],';
	}
	%sar_swap_stat = ();
	if (scalar keys %swap_stat > 0) {
		$swap_stat{'pswpin/s'} =~ s/,$//;
		$swap_stat{'pswpout/s'} =~ s/,$//;
		print &flotr2_linegraph_array($IDX++, 'system-swap', $data_info, '', $swap_stat{'pswpin/s'}, $swap_stat{'pswpout/s'});
	}
}

sub compute_page_stat
{
	for (my $i = 0; $i <= $#_; $i++) {
		# hostname;interval;timestamp;pgpgin/s;pgpgout/s;fault/s;majflt/s;pgfree/s;pgscank/s;pgscand/s;pgsteal/s;%vmeff
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));

		map { s/,/\./ } @data ;
		$data[3] ||= 0;
		$data[4] ||= 0;
		$data[6] ||= 0;
		if ($ACTION ne 'home') {
			$sar_pageswap_stat{$data[2]}{'pgpgin/s'}  = $data[3];
			$sar_pageswap_stat{$data[2]}{'pgpgout/s'} = $data[4];
			$sar_pageswap_stat{$data[2]}{'majflt/s'}  = $data[6];
		} else {
			if (!exists $OVERALL_STATS{'system'}{'pgpgin'} || ($OVERALL_STATS{'system'}{'pgpgin'}[1] < $data[3])) {
				@{$OVERALL_STATS{'system'}{'pgpgin'}} = ($data[2], $data[3]);
			}
			if (!exists $OVERALL_STATS{'system'}{'pgpgout'} || ($OVERALL_STATS{'system'}{'pgpgout'}[1] < $data[4])) {
				@{$OVERALL_STATS{'system'}{'pgpgout'}} = ($data[2], $data[4]);
			}
			if (!exists $OVERALL_STATS{'system'}{'majflt'} || ($OVERALL_STATS{'system'}{'majflt'}[1] < $data[6])) {
				@{$OVERALL_STATS{'system'}{'majflt'}} = ($data[2], $data[6]);
			}
		}
	}
}

sub compute_page_report
{
	my $data_info = shift();

	my %pageswap_stat = ();
	foreach my $t (sort {$a <=> $b} keys %sar_pageswap_stat) {
		$pageswap_stat{'pgpgin/s'}  .= '[' . $t . ',' . $sar_pageswap_stat{$t}{'pgpgin/s'} . '],';
		$pageswap_stat{'pgpgout/s'} .= '[' . $t . ',' . $sar_pageswap_stat{$t}{'pgpgout/s'} . '],';
		$pageswap_stat{'majflt/s'}  .= '[' . $t . ',' . $sar_pageswap_stat{$t}{'majflt/s'} . '],';
	}
	%sar_pageswap_stat = ();
	if (scalar keys %pageswap_stat > 0) {
		$pageswap_stat{'pgpgin/s'} =~ s/,$//;
		$pageswap_stat{'pgpgout/s'} =~ s/,$//;
		$pageswap_stat{'majflt/s'} =~ s/,$//;
		print &flotr2_linegraph_array($IDX++, 'system-page', $data_info, '', $pageswap_stat{'pgpgin/s'}, $pageswap_stat{'pgpgout/s'}, $pageswap_stat{'majflt/s'});
	}
}

sub compute_block_stat
{
	for (my $i = 0; $i <= $#_; $i++) {
		# hostname;interval;timestamp;tps;rtps;wtps;bread/s;bwrtn/s
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));

		map { s/,/\./ } @data;
		$data[6] ||= 0;
		$data[7] ||= 0;
		if ($ACTION ne 'home') {
			$sar_block_stat{$data[2]}{'bread/s'} = $data[6];
			$sar_block_stat{$data[2]}{'bwrtn/s'} = $data[7];
			$sar_block_stat{$data[2]}{'tps'} = ($data[3]||0);
			$sar_block_stat{$data[2]}{'rtps'} = ($data[4]||0);
			$sar_block_stat{$data[2]}{'wtps'} = ($data[5]||0);
		} else {
			if (!exists $OVERALL_STATS{'system'}{'bread'} || ($OVERALL_STATS{'system'}{'bread'}[1] < $data[6])) {
				@{$OVERALL_STATS{'system'}{'bread'}} = ($data[2], $data[6]);
			}
			if (!exists $OVERALL_STATS{'system'}{'bwrite'} || ($OVERALL_STATS{'system'}{'bwrite'}[1] < $data[7])) {
				@{$OVERALL_STATS{'system'}{'bwrite'}} = ($data[2], $data[7]);
			}
		}
	}
}

sub compute_block_report
{
	my $data_info = shift();

	my %block_stat = ();
	foreach my $t (sort {$a <=> $b} keys %sar_block_stat) {
		$block_stat{'bread/s'} .= '[' . $t . ',' . $sar_block_stat{$t}{'bread/s'} . '],';
		$block_stat{'bwrtn/s'} .= '[' . $t . ',' . $sar_block_stat{$t}{'bwrtn/s'} . '],';
		$block_stat{'tps'} .= '[' . $t . ',' . $sar_block_stat{$t}{'tps'} . '],';
		$block_stat{'rtps'} .= '[' . $t . ',' . $sar_block_stat{$t}{'rtps'} . '],';
		$block_stat{'wtps'} .= '[' . $t . ',' . $sar_block_stat{$t}{'wtps'} . '],';
	}
	if (scalar keys %block_stat > 0) {
		if ($data_info->{name} eq 'system-block') {
			%sar_block_stat = ();
			$block_stat{'bread/s'} =~ s/,$//;
			$block_stat{'bwrtn/s'} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'system-block', $data_info, '', $block_stat{'bread/s'}, $block_stat{'bwrtn/s'});
		} elsif ($data_info->{name} eq 'system-tps') {
			$block_stat{'tps'} =~ s/,$//;
			$block_stat{'rtps'} =~ s/,$//;
			$block_stat{'wtps'} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'system-tps', $data_info, '', $block_stat{'tps'}, $block_stat{'rtps'}, $block_stat{'wtps'});
		}
	}
}

sub compute_srvtime_stat
{


	for (my $i = 0; $i <= $#_; $i++) {
		# hostname;interval;timestamp;DEV;tps;rd_sec/s;wr_sec/s;avgrq-sz;avgqu-sz;await;svctm;%util
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));
		next if (!&device_in_report($data[3]));

		next if ($DEVICE && ($data[3] ne $DEVICE));

		map { s/,/\./ } @data ;
		$data[10] ||= 0;
		if ($ACTION ne 'home') {
			$sar_srvtime_stat{$data[2]}{$data[3]}{'await'} = ($data[9]||0);
			$sar_srvtime_stat{$data[2]}{$data[3]}{'svctm'} = $data[10];
		} else {
			if (!exists $OVERALL_STATS{'system'}{'svctm'} || ($OVERALL_STATS{'system'}{'svctm'}[1] < $data[10])) {
				@{$OVERALL_STATS{'system'}{'svctm'}} = ($data[2], $data[10], $data[3]);
			}
		}
	}
}

sub compute_srvtime_report
{
	my $data_info = shift();
	my $src_base = shift();

	my %srvtime_stat = ();
	foreach my $t (sort {$a <=> $b} keys %sar_srvtime_stat) {
		foreach my $dev (keys %{$sar_srvtime_stat{$t}}) {
			$srvtime_stat{$dev}{'await'} .= '[' . $t . ',' . $sar_srvtime_stat{$t}{$dev}{'await'} . '],';
			$srvtime_stat{$dev}{'svctm'} .= '[' . $t . ',' . $sar_srvtime_stat{$t}{$dev}{'svctm'} . '],';
		}
	}
	%sar_srvtime_stat = ();
	if (scalar keys %srvtime_stat > 0) {
		foreach my $n (sort { $a cmp $b } keys %srvtime_stat) {
			$srvtime_stat{$n}{'await'} =~ s/,$//;
			$srvtime_stat{$n}{'svctm'} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'system-srvtime', $data_info, $n, $srvtime_stat{$n}{'svctm'}, $srvtime_stat{$n}{'await'});
		}
	}
}

sub compute_rw_device_stat
{

	for (my $i = 0; $i <= $#_; $i++) {
		# hostname;interval;timestamp;DEV;tps;rd_sec/s;wr_sec/s;avgrq-sz;avgqu-sz;await;svctm;%util
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));
		next if (!&device_in_report($data[3]));

		next if ($DEVICE && ($data[3] ne $DEVICE));
		map { s/,/\./ } @data ;
		$data[4] ||= 0;
		$data[5] ||= 0;
		$data[6] ||= 0;
		if ($ACTION ne 'home') {
			$sar_rw_devices_stat{$data[2]}{$data[3]}{'rd_sec/s'} = ($data[5]*512);
			$sar_rw_devices_stat{$data[2]}{$data[3]}{'wr_sec/s'} = ($data[6]*512);
			$sar_rw_devices_stat{$data[2]}{$data[3]}{'tps'}      = $data[4];
		} else {
			$OVERALL_STATS{'system'}{'devices'}{$data[3]}{read} += ($data[5]*512);
			$OVERALL_STATS{'system'}{'devices'}{$data[3]}{write} += ($data[6]*512);
			$OVERALL_STATS{'system'}{'devices'}{$data[3]}{tps} = $data[4] if (!$OVERALL_STATS{'system'}{'devices'}{$data[3]}{tps} || ($OVERALL_STATS{'system'}{'devices'}{$data[3]}{tps} < $data[4]))
		}
	}
}

sub compute_rw_device_report
{
	my $data_info = shift();
	my $src_base = shift();

	my %devices_stat = ();
	foreach my $t (sort {$a <=> $b} keys %sar_rw_devices_stat) {
		foreach my $dev (keys %{$sar_rw_devices_stat{$t}}) {
			if ($data_info->{name} eq 'system-rwdevice') { 
				$devices_stat{$dev}{'rd_sec/s'} .= '[' . $t . ',' . $sar_rw_devices_stat{$t}{$dev}{'rd_sec/s'} . '],';
				$devices_stat{$dev}{'wr_sec/s'} .= '[' . $t . ',' . $sar_rw_devices_stat{$t}{$dev}{'wr_sec/s'} . '],';
			} elsif ($data_info->{name} eq 'system-tpsdevice') {
				$devices_stat{$dev}{'tps'}      .= '[' . $t . ',' . $sar_rw_devices_stat{$t}{$dev}{'tps'} . '],';
			}
		}
	}

	if (scalar keys %devices_stat > 0) {
		foreach my $n (sort { $a cmp $b } keys %devices_stat) {
			if ($data_info->{name} eq 'system-rwdevice') { 
				$devices_stat{$n}{'rd_sec/s'} =~ s/,$//;
				$devices_stat{$n}{'wr_sec/s'} =~ s/,$//;
				print &flotr2_linegraph_array($IDX++, 'system-rwdevice', $data_info, $n, $devices_stat{$n}{'rd_sec/s'}, $devices_stat{$n}{'wr_sec/s'});
			} elsif ($data_info->{name} eq 'system-tpsdevice') {
				$devices_stat{$n}{'tps'} =~ s/,$//;
				print &flotr2_linegraph_array($IDX++, 'system-tpsdevice', $data_info, $n, $devices_stat{$n}{'tps'});
			}
		}
	}
}

sub compute_util_device_stat
{
	for (my $i = 0; $i <= $#_; $i++) {
		# hostname;interval;timestamp;DEV;tps;rd_sec/s;wr_sec/s;avgrq-sz;avgqu-sz;await;svctm;%util
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));
		next if (!&device_in_report($data[3]));

		next if ($data[3] ne $DEVICE);

		map { s/,/\./ } @data ;
		$sar_util_devices_stat{$data[2]}{$data[3]}{'%util'} = ($data[11]||0);
	}
}

sub compute_util_device_report
{
	my $data_info = shift();
	my $src_base = shift();

	return if ($ACTION eq 'home');

	my %devices_stat = ();
	foreach my $t (sort {$a <=> $b} keys %sar_util_devices_stat) {
		foreach my $dev (keys %{$sar_util_devices_stat{$t}}) {
			$devices_stat{$dev}{'%util'} .= '[' . $t . ',' . $sar_util_devices_stat{$t}{$dev}{'%util'} . '],';
		}
	}
	%sar_util_devices_stat = ();
	if (scalar keys %devices_stat > 0) {
		foreach my $n (sort { $a cmp $b } keys %devices_stat) {
			$devices_stat{$n}{'%util'} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'system-cpudevice', $data_info, $n, $devices_stat{$n}{'%util'});
		}
	}
}

sub compute_network_stat
{
	for (my $i = 0; $i <= $#_; $i++) {
		# hostname;interval;timestamp;IFACE;rxpck/s;txpck/s;rxkB/s;txkB/s;rxcmp/s;txcmp/s;rxmcst/s
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));
		next if (!&interface_in_report($data[3]));

		next if ($data[3] ne $DEVICE);

		map { s/,/\./ } @data ;
		$sar_networks_stat{$data[2]}{$data[3]}{'rxkB/s'} = ($data[6]*1024);
		$sar_networks_stat{$data[2]}{$data[3]}{'txkB/s'} = ($data[7]*1024);
	}
}

sub compute_network_report
{
	my $data_info = shift();
	my $src_base = shift();

	return if ($ACTION eq 'home');

	my %networks_stat = ();
	foreach my $t (sort {$a <=> $b} keys %sar_networks_stat) {
		foreach my $dev (keys %{$sar_networks_stat{$t}}) {
			$networks_stat{$dev}{'rxkB/s'} .= '[' . $t . ',' . $sar_networks_stat{$t}{$dev}{'rxkB/s'} . '],';
			$networks_stat{$dev}{'txkB/s'} .= '[' . $t . ',' . $sar_networks_stat{$t}{$dev}{'txkB/s'} . '],';
		}
	}
	%sar_networks_stat = ();
	
	if (scalar keys %networks_stat > 0) {
		foreach my $n (sort { $a cmp $b } keys %networks_stat) {
			$networks_stat{$n}{'rxkB/s'} =~ s/,$//;
			$networks_stat{$n}{'txkB/s'} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'network-utilization', $data_info, $n, $networks_stat{$n}{'rxkB/s'}, $networks_stat{$n}{'txkB/s'});
		}
	}
}

sub compute_network_error_stat
{
	for (my $i = 0; $i <= $#_; $i++) {
		# hostname;interval;timestamp;IFACE;rxerr/s;txerr/s;coll/s;rxdrop/s;txdrop/s;txcarr/s;rxfram/s;rxfifo/s;txfifo/s
		my @data = split(/;/, $_[$i]);
		next if ($data[2] !~ /^\d+/);

		# Skip unwanted lines
		next if ($BEGIN && ($data[2] < $BEGIN));
		next if ($END   && ($data[2] > $END));
		next if (!&interface_in_report($data[3]));

		next if ($data[3] ne $DEVICE);

		map { s/,/\./ } @data ;
		$sar_neterror_stat{$data[2]}{$data[3]}{'rxerr/s'} = $data[4] || 0;
		$sar_neterror_stat{$data[2]}{$data[3]}{'txerr/s'} = $data[5] || 0;
		$sar_neterror_stat{$data[2]}{$data[3]}{'coll/s'}  = $data[6] || 0;
	}
}

sub compute_network_error_report
{
	my $data_info = shift();
	my $src_base = shift();

	return if ($ACTION eq 'home');

	my %errors_stat = ();
	foreach my $t (sort {$a <=> $b} keys %sar_networks_stat) {
		foreach my $dev (keys %{$sar_networks_stat{$t}}) {
			$errors_stat{$dev}{'rxerr/s'} .= '[' . $t . ',' . $sar_neterror_stat{$t}{$dev}{'rxerr/s'} . '],';
			$errors_stat{$dev}{'txerr/s'} .= '[' . $t . ',' . $sar_neterror_stat{$t}{$dev}{'txerr/s'} . '],';
			$errors_stat{$dev}{'coll/s'}  .= '[' . $t . ',' . $sar_neterror_stat{$t}{$dev}{'coll/s'} . '],';
		}
	}
	if (scalar keys %errors_stat > 0) {
		foreach my $n (sort { $a cmp $b } keys %errors_stat) {
			$errors_stat{$n}{'rxerr/s'} =~ s/,$//;
			$errors_stat{$n}{'txerr/s'} =~ s/,$//;
			$errors_stat{$n}{'coll/s'} =~ s/,$//;
			print &flotr2_linegraph_array($IDX++, 'network-error', $data_info, $n, $errors_stat{$n}{'rxerr/s'}, $errors_stat{$n}{'txerr/s'}, $errors_stat{$n}{'coll/s'});
		}
	}
}

sub compute_sarstat_stats
{
	my ($file, %data_info) = @_;

	####
	# Get CPU utilization
	####
	if ($data_info{name} eq 'system-cpu') {
		my $command = "$SADF_PROG -t -P ALL -D $file";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute cpu statistics
		&compute_cpu_stat(@content);
	}

	####
	# Get load average
	####
	if ($data_info{name} eq 'system-load') {
		my $command = "$SADF_PROG -t -D $file -- -q";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute load statistics
		&compute_load_stat(@content);
	}

	####
	# Get process number
	####
	if ($data_info{name} eq 'system-process') {
		my $command = "$SADF_PROG -t -D $file -- -q";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute process statistics
		&compute_process_stat(@content);
	}

	####
	# Get context swiches
	####
	if ($data_info{name} eq 'system-cswch') {
		my $command = "$SADF_PROG -t -D $file -- -w";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute context switches statistics
		&compute_context_stat(@content);
	}

	####
	# Get memory utilization
	####
	if ($data_info{name} eq 'system-memory') {
		my $command = "$SADF_PROG -t -D $file -- -r";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute graphs for memory statistics
		&compute_memory_stat(@content);
	}

	####
	# Get swap utilization
	####
	if ($data_info{name} eq 'system-swap') {
		my $command = "$SADF_PROG -t -D $file -- -W";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute swap statistics
		&compute_swap_stat(@content);
	}

	####
	# Get page utilization
	####
	if ($data_info{name} eq 'system-page') {
		my $command = "$SADF_PROG -t -D $file -- -B";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute page swap statistics
		&compute_page_stat(@content);
	}

	####
	# Get block in/out
	####
	if ($data_info{name} eq 'system-block') {
		my $command = "$SADF_PROG -t -D $file -- -b";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute block statistics
		&compute_block_stat(@content);
	}

	####
	# Get Device service time
	####
	if ($data_info{name} eq 'system-srvtime') {
		my $command = "$SADF_PROG -t -P ALL -D $file -- -d -p";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute service time per devices statistics
		&compute_srvtime_stat(@content);
	}


	####
	# Get Device block read/write utilization
	####
	if ($data_info{name} eq 'system-rwdevice') {
		my $command = "$SADF_PROG -t -P ALL -D $file -- -d -p";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute I/O per devices statistics
		&compute_rw_device_stat(@content);
	}

	####
	# When we are on home report we just collect overall stats. The following
	# statistiques are not necessary so we can return immediatly from the function
	####
	return if ($ACTION eq 'home');

	####
	# Get run queue length
	####
	if ($data_info{name} eq 'system-runqueue') {
		my $command = "$SADF_PROG -t -D $file -- -q";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute runqueue statistics
		&compute_process_stat(@content);
	}


	####
	# Get tasks created per second
	####
	if ($data_info{name} eq 'system-pcrea') {
		my $command = "$SADF_PROG -t -D $file -- -w";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute process creation statistics
		&compute_context_stat(@content);
	}


	####
	# Get TPS
	####
	if ($data_info{name} eq 'system-tps') {
		my $command = "$SADF_PROG -t -D $file -- -b";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute block statistics
		&compute_block_stat(@content);
	}


	####
	# Get per device TPS utilization
	####
	if ($data_info{name} eq 'system-tpsdevice') {
		my $command = "$SADF_PROG -t -P ALL -D $file -- -d -p";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute I/O per devices statistics
		&compute_rw_device_stat(@content);
	}

	####
	# Get Device utilization
	####
	if ($data_info{name} eq 'system-cpudevice') {
		my $command = "$SADF_PROG -t -P ALL -D $file -- -d -p";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute cpu utilization per devices statistics
		&compute_util_device_stat(@content);
	}


	####
	# Get network interface utilization
	####
	if ($data_info{name} eq 'network-utilization') {
		my $command = "$SADF_PROG -t -P ALL -D $file -- -n DEV";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute network statistics
		&compute_network_stat(@content);
	}

	####
	# Get network errors utilization
	####
	if ($data_info{name} eq 'network-error') {
		my $command = "$SADF_PROG -t -P ALL -D $file -- -n EDEV";
		print STDERR "DEBUG: running $command'\n" if ($DEBUG);
		# Load data from file
		if (!open(IN, "$command |")) {
			die "FATAL: can't read output from command ($command): $!\n";
		}
		my @content = <IN>;
		close(IN);
		chomp(@content);

		# Compute network errors statistics
		&compute_network_error_stat(@content);
	}
}

sub find_report_type
{
	my $data = shift;
	my $type = '';

	if ($data =~ m#cswch/s#) {
		$type = 'cswch';
	} elsif ($data =~ m#proc/s#) {
		$type = 'pcrea';
	} elsif ($data =~ m#CPU\s+i\d+#) {
		$type = 'ncpu';
	} elsif ($data =~ m#CPU\s+M#) {
		$type = 'scpu';
	} elsif ($data =~ m#CPU\s+w#) {
		$type = 'wcpu';
	} elsif ($data =~ m#CPU\s+#) {
		$type = 'cpu';
	} elsif ($data =~ m#INTR\s+#) {
		$type = 'intr';
	} elsif ($data =~ m#pgpgin/s\s+#) {
		$type = 'page';
	} elsif ($data =~ m#pswpin/s\s+#) {
		$type = 'pswap';
	} elsif ( ($data =~ m#tps\s+#) && ($data !~ m#DEV\s+#) ) {
		$type = 'io';
	} elsif ($data =~ m#frmpg/s\s+#) {
		$type = 'mpage';
	} elsif ($data =~ m#TTY\s+#) {
		$type = 'tty';
	} elsif ($data =~ m#IFACE\s+rxpck/s\s+#) {
		$type = 'net';
	} elsif ($data =~ m#IFACE\s+rxerr/s\s+#) {
		$type = 'err';
	} elsif ($data =~ m#DEV\s+#) {
		$type = 'dev';
	} elsif ($data =~ m#kbmemfree\s+#) {
		$type = 'mem';
	# New in sysstat 8.1.5
	} elsif ($data =~ m#kbswpfree\s+#) {
		$type = 'swap';
	} elsif ($data =~ m#dentunusd\s+#) {
		$type = 'file';
	} elsif ($data =~ m#totsck\s+#) {
		$type = 'sock';
	} elsif ($data =~ m#runq-sz\s+#) {
		$type = 'load';
	# New in 8.1.7
	} elsif ($data =~ m#active\/s\s+#) {
		$type = 'tcp';
	}

	return $type;
}

sub compute_sarfile_stats
{
	my ($file, %data_info) = @_;

	my $interval = 0;
	my $hostname = 'unknown';

	# Load data from file
	if (!is_compressed($file)) {
		open(IN, $file) or die "ERROR: can't read file $file, $!\n";
	} else {
		open(IN, "$ZCAT_PROG $file |") or die "ERROR: can't read pipe on command: $ZCAT_PROG $file, $!\n";
	}
	my @content = ();
	while (my $l = <IN>) {
		chomp($l);
		$l =~ s/\r//;
		# Skip kernel header part
		if ( ($l eq '') || ($l =~ /^\d+:\d+:\d+/) || ($l =~ /\d+\/\d+\/\d+/)) {
			push(@content, $l);
		}
	}
	close(IN);

	my $type = '';
	my @headers = ();
	my %fulldata = ();
	my $old_time = 0;
	my $orig_time = 0;

	for (my $i = 0; $i <= $#content; $i++) {

		# Empty line, maybe the end of a report
		if ($content[$i] eq '') {
			$type = '';
			@headers = ();
			$old_time = 0 if ($FROM_SA_FILE);
			next;
		}
		# look for kernel header to find the date
		if ( ($content[$i] !~ /^\d+:\d+:\d+/) && ($content[$i] =~ /(\d+)\/(\d+)\/(\d+)/) ) {
			$sar_month = $1;
			$sar_day = $2;
			$sar_year = $3;
			if (length($sar_year) == 2) {
				$sar_year += 2000;
			}
			if ($REVERT_DATE || ($sar_month > 12)) {
				my $tmp = $sar_day;
				$sar_day = $sar_month;
				$sar_month = $tmp;
			}
			$type = '';
			@headers = ();
			next;
		}
		# Remove average header if any
		if ( ($content[$i] !~ /^\d+:\d+:\d+/) && ($content[$i] =~ /^\D:\s+/) ) {
			$type = '';
			@headers = ();
			next;
		}

		if ($#headers == -1) {
			push(@headers, split(m#\s+#, $content[$i]));
			shift(@headers);
			# Try to find the kind of report
			$type = &find_report_type($content[$i]);
			if (!$type) {
				@headers = ();
			} else {
				push(@{$fulldata{$type}}, "hostname;interval;timestamp;" . join(";", @headers));
			}
			next;
		}

		# Remove AM|PM timestamp information
		my $am_pm = '';
		if ($content[$i] =~ s/^(\d+:\d+:\d+)\s(AM|PM)/$1/) {
			$am_pm = $2;
			shift(@headers) if ($headers[0] =~ /^(AM|PM)$/);
		}
		# Get all values reported
		my @values = ();
		push(@values, split(m#\s+#, $content[$i]));
		# Extract the timestamp of the line
		my $timestamp = shift(@values);

		if ($#values != $#headers) {
			warn "ERROR: Parsing of sar output reports different values than headers allow. ($#values != $#headers)\n";
			die "Header: " . join(';', @headers) . " | Values: " . join(';', @values) . "\n";
		}
		if ($timestamp =~ /(\d+:\d+:\d+)/) {
			$timestamp = &convert_sar_time($1, $old_time, $am_pm);
			$old_time = $timestamp;
		}
		if (!$timestamp) {
			print STDERR "ERROR: unkown time information from sar file.\n";
			print STDERR "HEADER: $timestamp ", join(" ", @headers), "\n";
			die "DATA: $content[$i]\n";
		}

		# Change decimal character to perl
		map { s/,/\./; } @values;
		push(@{$fulldata{$type}}, "$hostname;$interval;$timestamp;" . join(";", @values));
	}
	@content = ();

	####
	# Set CPU utilization
	####
	if ($data_info{name} eq 'system-cpu') {

		# Compute cpu statistics
		&compute_cpu_stat(@{$fulldata{cpu}});

	}

	####
	# Set load average
	####
	if ($data_info{name} eq 'system-load') {

		# Compute load statistics
		&compute_load_stat(@{$fulldata{load}});

	}

	####
	# Set process number
	####
	if ($data_info{name} eq 'system-process') {

		# Compute process statistics
		&compute_process_stat(@{$fulldata{load}});

	}

	####
	# Set context switches
	####
	if ($data_info{name} eq 'system-cswch') {

		# Compute context switches statistics
		&compute_context_stat(@{$fulldata{cswch}});

	}

	####
	# Set memory utilization
	####
	if ($data_info{name} eq 'system-memory') {

		# Compute memory statistics
		&compute_memory_stat(@{$fulldata{mem}});

	}

	####
	# Set swap utilization
	####
	if ($data_info{name} eq 'system-swap') {

		# Compute swap statistics
		&compute_swap_stat(@{$fulldata{pswap}});

	}

	####
	# Set page utilization
	####
	if ($data_info{name} eq 'system-page') {

		# Compute page swap statistics
		&compute_page_stat(@{$fulldata{page}});

	}

	####
	# Set block in/out
	####
	if ($data_info{name} eq 'system-block') {

		# Compute block statistics
		&compute_block_stat(@{$fulldata{io}});

	}

	####
	# Set Device service time
	####
	if ($data_info{name} eq 'system-srvtime') {

		# Compute service time per devices statistics
		&compute_srvtime_stat(@{$fulldata{dev}});

	}

	####
	# Set Device read/write utilization
	####
	if ($data_info{name} eq 'system-rwdevice') {

		# Compute I/O per devices statistics
		&compute_rw_device_stat(@{$fulldata{dev}});

	}

	####
	# When we are on home report we just collect overall stats. The following
	# statistiques are not necessary so we can return immediatly from the function
	####
	return if ($ACTION eq 'home');

	####
	# Set run queue length
	####
	if ($data_info{name} eq 'system-runqueue') {

		# Compute runqueue statistics
		&compute_process_stat(@{$fulldata{load}});

	}

	####
	# Set process created per second
	####
	if ($data_info{name} eq 'system-pcrea') {

		# Compute process created per second statistics
		&compute_context_stat(@{$fulldata{cswch}});

	}

	####
	# Set TPS
	####
	if ($data_info{name} eq 'system-tps') {

		# Compute block statistics
		&compute_block_stat(@{$fulldata{io}});

	}


	####
	# Set Device read/write utilization
	####
	if ($data_info{name} eq 'system-tpsdevice') {

		# Compute I/O per devices statistics
		&compute_rw_device_stat(@{$fulldata{dev}});

	}

	####
	# Set Device utilization
	####
	if ($data_info{name} eq 'system-cpudevice') {

		# Compute cpu utilization per devices statistics
		&compute_util_device_stat(@{$fulldata{dev}});

	}

	####
	# Set network utilization
	####
	if ($data_info{name} eq 'network-utilization') {

		# Compute block statistics
		&compute_network_stat(@{$fulldata{net}});

	}

	####
	# Set network error utilization
	####
	if ($data_info{name} eq 'network-error') {

		# Compute network error statistics
		&compute_network_error_stat(@{$fulldata{err}});

	}

}

sub compute_sar_graph
{
	my ($src_base, %data_info) = @_;

	####
	# Show CPU utilization
	####
	if ($data_info{name} eq 'system-cpu') {

		# Compute graphs for cpu statistics
		&compute_cpu_report(\%data_info);

	}

	####
	# Show load average
	####
	if ($data_info{name} eq 'system-load') {

		# Compute graphs for load statistics
		&compute_load_report(\%data_info);

	}

	####
	# Show process number
	####
	if ($data_info{name} eq 'system-process') {

		# Compute graphs for process statistics
		&compute_process_report(\%data_info);

	}

	####
	# Show run queue length
	####
	if ($data_info{name} eq 'system-runqueue') {

		# Compute graphs for runqueue statistics
		&compute_process_report(\%data_info);

	}

	####
	# Show context switches
	####
	if ($data_info{name} eq 'system-cswch') {

		# Compute graphs for context switches statistics
		&compute_context_report(\%data_info);

	}

	####
	# Show process created per second
	####
	if ($data_info{name} eq 'system-pcrea') {

		# Compute graphs for number of process created per second statistics
		&compute_context_report(\%data_info);

	}

	####
	# Show memory utilization
	####
	if ($data_info{name} eq 'system-memory') {

		# Compute graphs for memory statistics
		&compute_memory_report(\%data_info);

	}

	####
	# Show swap utilization
	####
	if ($data_info{name} eq 'system-swap') {

		# Compute graphs for swap statistics
		&compute_swap_report(\%data_info);

	}

	####
	# Show page utilization
	####
	if ($data_info{name} eq 'system-page') {

		# Compute graphs for page swap statistics
		&compute_page_report(\%data_info);

	}

	####
	# Show block in/out
	####
	if ($data_info{name} eq 'system-block') {

		# Compute graphs for block statistics
		&compute_block_report(\%data_info);

	}

	####
	# Show TPS
	####
	if ($data_info{name} eq 'system-tps') {

		# Compute graphs for block statistics
		&compute_block_report(\%data_info);

	}


	####
	# Show Device service time
	####
	if ($data_info{name} eq 'system-srvtime') {

		# Compute graphs for service time per device statistics
		&compute_srvtime_report(\%data_info, $src_base);

	}

	####
	# Show Device read/write utilization
	####
	if ($data_info{name} eq 'system-rwdevice') {

		# Compute graphs for I/O per devices statistics
		&compute_rw_device_report(\%data_info, $src_base);

	}

	####
	# Show per device TPS utilization
	####
	if ($data_info{name} eq 'system-tpsdevice') {

		# Compute graphs for I/O per devices statistics
		&compute_rw_device_report(\%data_info, $src_base);

	}

	####
	# Show Device utilization
	####
	if ($data_info{name} eq 'system-cpudevice') {

		# Compute graphs for cpu utilization per devices statistics
		&compute_util_device_report(\%data_info, $src_base);

	}

	####
	# Show network utilization
	####
	if ($data_info{name} eq 'network-utilization') {

		# Compute graphs for network utilization statistics
		&compute_network_report(\%data_info, $src_base);

	}

	####
	# Show network error utilization
	####
	if ($data_info{name} eq 'network-error') {

		# Compute graphs for network errors statistics
		&compute_network_error_report(\%data_info, $src_base);

	}

}

sub convert_time
{
	my $str = shift;

	# 2012-07-16 12:35:29+02
	if ($str =~ /(\d+)-(\d+)-(\d+) (\d+):(\d+):(\d+)/) {
		return &timegm_nocheck($6, $5, $4, $3, $2 - 1, $1 - 1900) * 1000;
	} elsif ($str =~ /(\d+)-(\d+)-(\d+) (\d+):(\d+)/) {
		return &timegm_nocheck(0, $5, $4, $3, $2 - 1, $1 - 1900) * 1000;
	} elsif ($str =~ /(\d+):(\d+):(\d+)/) {
		return &timegm_nocheck($3, $2, $1, $o_day, $o_month - 1, $o_year - 1900) * 1000;
	} elsif ($str !~ /\D/) {
		return $str * 1000;
	}

	return $str;
}

sub convert_sar_time
{
	my ($str, $old_timestamp, $am_pm) = @_;

	my $curdate = '';

	$old_timestamp ||= 0;
	$sar_day ||= $o_day;
	$sar_month ||= $o_month;
	$sar_year ||= $o_year;

	if ($str =~ /(\d+):(\d+):(\d+)/) {
		my $h = $1;
		my $m = $2;
		my $s = $3;
		if ($am_pm && ($am_pm eq 'AM')) {
			$h = 0 if ($h == 12);
		} elsif ($am_pm && ($am_pm eq 'PM')) {
			$h += 12 if ($h < 12);
		}
			
		my $time = ($h*3600)+($m*60)+$s;

		my $tz = ((0-$TIMEZONE)*3600);
		$curdate = &timegm_nocheck(0, 0, 0, $sar_day, $sar_month - 1, $sar_year - 1900) + $tz;
		while ($old_timestamp > (($curdate+$time) * 1000)) {
			$curdate += 86399;
			my @tinf = gmtime($curdate - $tz);
			$sar_month = $tinf[4]+1;
			$sar_day = $tinf[3];
			$sar_year = $tinf[5]+1900;
		}

		return ($curdate + $time) * 1000;
	}

	return 0;
}

sub flotr2_linegraph_array
{
	my ($buttonid, $divid, $infos, $title, @data) = @_;

	my @legend = ();
	my $data2 = '';
	my $id = 1;
	for (my $i = 0; $i <= $#data; $i++) {
		next if (!$data[$i]);
		$data[$i] ||= '';
		$data[$i] = "var d$id = [$data[$i]];\n";
		my $color = '';
		if ($GRAPH_COLORS[$i]) {
			$color = ", color: \"$GRAPH_COLORS[$i]\"";
		}
		if ($infos->{y2label} && ($i == $#data)) {
			push(@legend, "{ data: d$id, label: \"" . ($infos->{legends}[$i] || '') . "\"$color, yaxis: 2 },\n");
		} else {
			push(@legend, "{ data: d$id, label: \"" . ($infos->{legends}[$i] || '') . "\"$color, mouse:{track:true} },\n");
		}
		$id++;
	}
	if ($title ne '') {
		$title = sprintf($infos->{title}, $title);
	} else {
		$title = $infos->{title};
	}
	return &flotr2_linegraph($buttonid, $divid, $infos, $title, \@data, \@legend);
}

sub flotr2_linegraph_hash
{
	my ($buttonid, $divid, $infos, $title, %data_h) = @_;

	my @legend = ();
	my @data = ();
	my $i = 1;
	foreach my $id (sort keys %data_h) {
		$data_h{$id} ||= '';
		my $color = '';
		if ($GRAPH_COLORS[$i]) {
			$color = ", color: \"$GRAPH_COLORS[$i]\"";
		}
		push(@data, "var d$i = [$data_h{$id}];\n");
		push(@legend, "{ data: d$i, label: \"$id\"$color, mouse:{track:true} },\n");
		$i++;
	}
	if ($title ne '') {
		$title = sprintf($infos->{title}, $title);
	} else {
		$title = $infos->{title};
	}

	return &flotr2_linegraph($buttonid, $divid, $infos, $title, \@data, \@legend);
}

sub flotr2_linegraph
{
	my ($buttonid, $divid, $infos, $title, $data, $legend) = @_;
	my $ylabel = $infos->{ylabel} || '';
	my $type = '';
	if ($ylabel =~ /size/i) {
		$type = 'size';
	} elsif ($ylabel =~ /mduration/i) {
		$type = 'mduration';
		$ylabel =~ s/m(duration)/$1/i;
	}
	my $description = $infos->{description} || '';
	my $str = '';
	if (($divid !~ /\+$/) && ($divid !~ /^statio-/)) {
		$str = qq{
<ul id="slides">
<li class="slide active-slide" id="$divid-slide">
      <div id="$divid"><br/><br/><br/><br/></div>
};
	} else {
		$divid =~ s/\+$//;
	}
	$str .= qq{
      <div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
              <h2>$title</h2>
		<p>$description</p>
              </div>
              <div class="panel-body">
};
	my $yaxis2 = '';
	if ($infos->{y2label}) {
		my $color = '';
		if ($GRAPH_COLORS[$#{$data}]) {
			$color = ", color: \"$GRAPH_COLORS[$#{$data}]\"";
		}
		my $y2label = $infos->{y2label} || '';
		$yaxis2 = "y2axis: { mode: \"normal\", title: \"$y2label\", min: 0$color },";
	}

	my $dateTracker_lblopts = '';
	my $dateTracker_dataopts = '';
	my $has_data = 0;
	if ($#{$data} >= 0) {
		for (my $i = 0; $i <= $#{$legend}; $i++) {
			next if (!$legend->[$i]);
			if ($legend->[$i] =~ /label: "([^"]+)"/) {
				$dateTracker_lblopts .= "'$1',";
			}
		}
		$dateTracker_lblopts =~ s/,$//;
		$dateTracker_lblopts = "[$dateTracker_lblopts]";

		for (my $i = 0; $i <= $#{$data}; $i++) {
			next if (!$data->[$i]);
			if ($data->[$i] =~ /var (d\d+) =/) {
				$dateTracker_dataopts .= "$1,";
				$has_data = 1;
			}
		}
		$dateTracker_dataopts =~ s/,$//;
		$dateTracker_dataopts = "[$dateTracker_dataopts]";
	}

	my $cssgraph = 'linegraph';
	my $write_buttons = "write_buttons($buttonid);";
	my $hnoTicks = 20;
	my $vnoTicks = 10;
	if ($divid =~ /^table-/) {
		$cssgraph = 'smallgraph';
		$write_buttons = '';
		$hnoTicks = 15;
		$vnoTicks = 4;
	}

	if ($has_data) {
		$str .= <<EOF;
<div id="$divid$buttonid" class="$cssgraph"></div>
<script type="text/javascript">
(function mouse_zoom(container) {

    $write_buttons
@$data
    var options = {
        xaxis: {
	    tickDecimals: 0,
	    noTicks: $hnoTicks,
	    mode: "time",
	    labelsAngle: 45
        },
        yaxis: {
            mode: "normal",
	    noTicks: $vnoTicks,
            title: "$ylabel",
	    tickFormatter: function(val){ return pretty_print_number(val,'$type') },

        },
	$yaxis2
        selection: {
            mode: "x",
            fps: 30
        },
        title: "$title",
        legend: {
            position: "nw",
            backgroundColor: "#D2E8FF",
            backgroundOpacity: 0.4
        },
	mouse: {
	    track: true,
	    trackFormatter: function(obj){ return dateTracker(obj,'$type',$dateTracker_lblopts,$dateTracker_dataopts) },
	    relative: true,
	    sensibility: 5,
	    trackDecimals: 2,
	    lineColor: 'purple',
        },
        crosshair: {
            mode: 'x',
            color: '#000000',
            hideCursor: false,
        },
        HtmlText: false,
    };

    function drawGraph(opts) {
        var o = Flotr._.extend(Flotr._.clone(options), opts );
        return Flotr.draw(
        	container,
        	[
@$legend
    		],
    		o
    	);
    }

    var graph = drawGraph();
    Flotr.EventAdapter.observe(container, "flotr:select", function(area) {
        f = drawGraph({
            xaxis: {
            mode: "time",
            labelsAngle: 45,
                min: area.x1,
                max: area.x2
            },
            yaxis: {
                min: area.y1,
                max: area.y2,
		tickFormatter: function(val){ return pretty_print_number(val,'$type') },
            }
        });
    });
    Flotr.EventAdapter.observe(container, "flotr:click", function() {
        drawGraph();
    });
    document.getElementById('reset$buttonid').onclick = function() {
      graph.download.restoreCanvas();
    };
    document.getElementById('download$buttonid').onclick = function() {
	if (Flotr.isIE && Flotr.isIE < 9) {
		alert(browser_warning);
	}
      graph.download.saveImage('$IMG_FORMAT');
    };
    document.getElementById('toimage$buttonid').onclick = function() {
	if (Flotr.isIE && Flotr.isIE < 9) {
		alert(browser_warning);
	}
      graph.download.saveImage('$IMG_FORMAT', null, null, true);
    };

})(document.getElementById("$divid$buttonid"));
</script>
EOF
	} else {
		$str .= '<div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div>';
	}
	$str .= qq{
              </div>
              </div>
            </div><!--/span-->
      </div>
};
	$str .= qq{
</li>
</ul>
} if ($divid !~ /^(pgbouncer|tablespace|statio)/);

	return $str;

}

sub flotr2_piegraph
{
	my ($buttonid, $divid, $infos, $title, %data) = @_;

	my @datadef = ();
	my @contdef = ();
	my $i = 1;
	foreach my $k (sort keys %data) {
		push(@datadef, "var d$i = [ [0,$data{$k}] ];\n");
		push(@contdef, "{ data: d$i, label: \"$k\" },\n");
		$i++;
	}

	if ($title ne '') {
		$title = sprintf($infos->{title}, $title);
	} else {
		$title = $infos->{title};
	}
	my $description = $infos->{description} || '';
	my $str = qq{
<ul id="slides">
<li class="slide active-slide" id="$divid-slide">
      <div id="$divid"><br/><br/><br/><br/></div>
      <div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
              <h2>$title</h2>
		<p>$description</p>
              </div>
              <div class="panel-body">

};

	if ($#datadef >= 0) {
		$str .= <<EOF;
<div id="$divid$buttonid" class="piegraph"></div>
<script type="text/javascript">
(function basic_pie(container) {

    write_buttons($buttonid);

    @datadef
    var graph = Flotr.draw(container, [
    @contdef
    ], {
        title: "$title",
        HtmlText: false,
        grid: {
            verticalLines: false,
            horizontalLines: false,
	    backgroundColor: '#ffffff',
	    outline: '',
        },
        xaxis: {
            showLabels: false
        },
        yaxis: {
            showLabels: false
        },
        pie: {
            show: true,
	    explode: 6
        },
        mouse: {
            track: true,
	    trackFormatter: function(obj){ return pieTracker(obj) },
	    relative: true
        },
        legend: {
            position: "sw",
            backgroundColor: "#D2E8FF",
	    backgroundOpacity: 0.4
        }
    });
    document.getElementById('reset$buttonid').onclick = function() {
      graph.download.restoreCanvas();
    };
    document.getElementById('download$buttonid').onclick = function(){
	if (Flotr.isIE && Flotr.isIE < 9) {
		alert(browser_warning);
	}
      graph.download.saveImage('$IMG_FORMAT');
    };
    document.getElementById('toimage$buttonid').onclick = function() {
	if (Flotr.isIE && Flotr.isIE < 9) {
		alert(browser_warning);
	}
      graph.download.saveImage('$IMG_FORMAT', null, null, true);
    };


})(document.getElementById("$divid$buttonid"));
</script>
EOF
	} else {
		$str .= '<div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div>';
	}
	$str .= qq{
              </div>
              </div>
            </div><!--/span-->
      </div>
</li>
</ul>
};

	return $str;
}

sub getNumericalOffset
{
	my $stringofs = shift;

	my @pieces = split /\//, $stringofs;
	die "Invalid offset: $stringofs" unless ($#pieces == 1);


	# First part is logid, second part is record offset
	return (hex("ffffffff") * hex($pieces[0])) + hex($pieces[1]);
}

sub read_sysinfo
{
	my $file = shift;

	if (!is_compressed($file)) {
		open(IN, $file) or die "ERROR: can't read file $file, $!\n";
	} else {
		open(IN, "$ZCAT_PROG $file |") or die "ERROR: can't read pipe on command: $ZCAT_PROG $file, $!\n";
	}
	my %sysinfo = ();
	my $section = '';
	while (my $l = <IN>) {
		chomp($l);
		if ($l =~ /^\[(.*)\]$/) {
			$section = $1;
			next;
		}
		if ($section eq 'CPU') {
			my ($key, $val) = split(/\s+:\s+/, $l);
			if ($key eq 'processor') {
				$sysinfo{$section}{$key} = $val + 1;
			} elsif ($key eq 'model name') {
				$val =~ s/\s+\@\s+(.*)$//;
				$sysinfo{$section}{'cpu MHz'} = $1;
				$sysinfo{$section}{$key} = $val;
			} else {
				$sysinfo{$section}{$key} = $val;
			}
		}
		if ($section eq 'KERNEL') {
			my @kinf = split(/\s+/, $l);
			$sysinfo{$section}{'hostname'} = $kinf[1];
			$sysinfo{$section}{'kernel'} = "$kinf[0] $kinf[2] $kinf[3] $kinf[4]";
			$sysinfo{$section}{'arch'} = "$kinf[-2] $kinf[-1]";
		}
		if ($section eq 'RELEASE') {
			my ($key, $val) = split(/=/, $l);
			if ($val) {
				$val =~ s/"//g;
				$sysinfo{$section}{lc($key)} = $val;
			} else {
				$sysinfo{RELEASE}{'name'} = $key;
				$sysinfo{RELEASE}{'version'} = '';
			}
		}
		if ($section eq 'MEMORY') {
			my ($key, $val) = split(/:\s+/, $l);
			if ($val =~ s/ kB//) {
				$sysinfo{$section}{lc($key)} = &pretty_print_size($val*1000);
			} else {
				$sysinfo{$section}{lc($key)} = $val;
			}
		}
		if ($section eq 'DF') {
			next if ($l !~ /^[\s\/]/);
			if ($l =~ s/^\s+//) {
				$sysinfo{$section}[-1] =~ s/<\/tr>$/<td>/;
				$sysinfo{$section}[-1] .= join('</td><td>', split(/\s+/, $l)) . "</td></tr>";
				next;
			}
			push(@{$sysinfo{$section}}, '<tr><td>' . join('</td><td>', split(/\s+/, $l)) . "</td></tr>");
		}
		if ($section eq 'MOUNT') {
			next if ($l !~ /^\//);
			push(@{$sysinfo{$section}}, '<tr><td>' . join('</td><td>', split(/\s+on\s+|\s+type\s+|\s+/, $l)) . '</td></tr>');
		}
		if ($section eq 'PCI') {
			push(@{$sysinfo{$section}}, "$l\n");
		}
		if ($section eq 'SYSTEM') {
			my ($key, $val) = split(/\s*[=:]\s+/, $l);
			$sysinfo{$section}{$key} = $val if ($key) and ($val);
		}
		if ($section eq 'PGVERSION') {
			$sysinfo{$section}{full_version} = $l;
			if ($l =~ /^PostgreSQL (\d+)\.(\d+)\.(\d+)/) {
				$sysinfo{$section}{major} = "$1.$2";
				$sysinfo{$section}{minor} = "$1.$2.$3";
			} elsif ($l =~ /^PostgreSQL (\d+)\.(\d+)/) {
				$sysinfo{$section}{major} = "$1.$2";
				$sysinfo{$section}{minor} = "$1.$2.0";
			} elsif ($l =~ /^EnterpriseDB (\d+)\.(\d+)\.(\d+)/) {
				$sysinfo{$section}{major} = "$1.$2";
				$sysinfo{$section}{minor} = "$1.$2.$3";
			} elsif ($l =~ /(\d+)\.(\d+)\.(\d+)/) {
				$sysinfo{$section}{major} = "$1.$2";
				$sysinfo{$section}{minor} = "$1.$2.$3";
			} else {
				$sysinfo{$section}{major} = '';
				$sysinfo{$section}{minor} = '';
			}
		}
		if ($section eq 'EXTENSION') {
			my ($db, @vals) = split(/[=,]+/, $l);
			push(@{$sysinfo{$section}{$db}}, @vals);
			foreach my $e (@vals) {
				push(@{$OVERALL_STATS{'cluster'}{'extensions'}}, $e) if (!grep(/^$e$/, @{$OVERALL_STATS{'cluster'}{'extensions'}}));
			}

		}
		if ($section eq 'SCHEMA') {
			my ($db, @vals) = split(/[=,]+/, $l);
			push(@{$sysinfo{$section}{$db}}, @vals);
		}
		if ($section eq 'PROCEDURE') {
			my ($db, @vals) = split(/[=,]+/, $l);
			push(@{$sysinfo{$section}{$db}}, @vals);
		}
		if ($section eq 'TRIGGER') {
			my ($db, $val) = split(/[=]+/, $l);
			$sysinfo{$section}{$db} = $val;
		}
		if ($section eq 'PROCESS') {
			my ($USER,$PID,$CPU,$MEM,$VSZ,$RSS,$TTY,$STAT,$START,$TIME,$COMMAND) = split(/\s+/, $l, 11);
			push(@{$sysinfo{$section}}, '<tr><td>' . join('</td><td>', $USER,$PID,$CPU,$MEM,$VSZ,$RSS,$TTY,$STAT,$START,$TIME,$COMMAND) . '</td></tr>') if ($l !~/^USER/);
		}
	}
	close(IN);

	return %sysinfo;
}

# Format duration
sub format_duration
{
	my $time = shift;

	return '0s' if (!$time);

	my $days = int($time / 86400000);
	$time -= ($days * 86400000);
	my $hours = int($time / 3600000);
	$time -= ($hours * 3600000);
	my $minutes = int($time / 60000);
	$time -= ($minutes * 60000);
	my $seconds = sprintf("%0.3f", $time / 1000);

	$days    = $days < 1    ? '' : $days . 'd';
	$hours   = $hours < 1   ? '' : $hours . 'h';
	$minutes = $minutes < 1 ? '' : $minutes . 'm';
	$seconds =~ s/\.\d+$// if ($minutes);
	$time    = $days . $hours . $minutes . $seconds . 's';

	return $time;
}

sub get_data_directories
{
	my @work_dirs = ();

	# Lookup for daily or hourly sub directories to scan
	# Search years / months / days / hours directories
	if (not opendir(DIR, "$INPUT_DIR")) {
		die "FATAL: Can't open directory $INPUT_DIR: $!\n";
	}
	my @years = grep { /^\d+$/ && -d "$INPUT_DIR/$_" } readdir(DIR);
	closedir(DIR);
	if ($#years >= 0) {
		foreach  my $y (sort { $a <=> $b } @years) {
			next if ($o_year && ($y < $o_year));
			next if ($e_year && ($y > $e_year));
			if (not opendir(DIR, "$INPUT_DIR/$y")) {
				die "FATAL: Can't open directory $INPUT_DIR/$y: $!\n";
			}
			my @months = grep { /^\d+$/ && -d "$INPUT_DIR/$y/$_" } readdir(DIR);
			closedir(DIR);
			foreach  my $m (sort { $a <=> $b } @months) {
				next if ($o_month && ($m < $o_month));
				next if ($e_month && ($m > $e_month));
				if (not opendir(DIR, "$INPUT_DIR/$y/$m")) {
					die "FATAL: Can't open directory $INPUT_DIR/$y/$m: $!\n";
				}
				my @days = grep { /^\d+$/ && -d "$INPUT_DIR/$y/$m/$_" } readdir(DIR);
				closedir(DIR);
				foreach  my $d (sort { $a <=> $b } @days) {
					next if ($o_day && ($d < $o_day));
					next if ($e_day && ($d > $e_day));
					if (not opendir(DIR, "$INPUT_DIR/$y/$m/$d")) {
						die "FATAL: Can't open directory $INPUT_DIR/$y/$m/$d: $!\n";
					}
					my @hours = grep { /^\d+$/ && -d "$INPUT_DIR/$y/$m/$d/$_" } readdir(DIR);
					closedir(DIR);
					if ($#hours == -1) {
						push(@work_dirs, "$y/$m/$d");
					} else {
						foreach  my $h (sort { $a <=> $b } @hours) {
							next if ($o_hour && ($h < $o_hour));
							next if ($e_hour && ($h > $e_hour));
							push(@work_dirs, "$y/$m/$d/$h");
						}
					}
				}
			}
		}

	} else {
		# we are not in incremental mode only first level directory will be proceed
		push(@work_dirs, '.');
	}

	return @work_dirs;
}

# Initialise global variables storing PostgreSQL statistics
sub clear_db_stats
{
	print STDERR "DEBUG: Cleaning memory from PostgreSQL statistics storages\n" if ($DEBUG);

	foreach my $name (@pg_to_be_stored) {
		if (grep(/^$name$/, 'global_databases', 'global_tbspnames', )) {
			@{$name} = ();
		} else {
			%{$name} = ();
		}
	}		
}


# Initialise global variables storing statistics
sub clear_stats
{
	# Clean PostgreSQL statistics
	&clear_db_stats();

	print STDERR "DEBUG: Cleaning memory from all statistics storages\n" if ($DEBUG);
	%OVERALL_STATS = ();
	%sysinfo = ();
	foreach my $name (@sar_to_be_stored) {
		%{$name} = ();
	}		

}

# Dump relevant memory to file for incremental use
sub dump_pg_binary
{
        my ($in_dir, $outfile) = @_;

	foreach my $name (@pg_to_be_stored) {
		my $lfh = new IO::File ">$in_dir/$name.bin";
		if (not defined $lfh) {
			die "FATAL: can't write to $in_dir/$name.bin, $!\n";
		}
		if (grep(/^$name$/, 'global_databases', 'global_tbspnames', )) {
			store_fd({ $name => \@{$name} }, $lfh) || die ("Couldn't save binary data to \"$in_dir/$name.bin\"!\n");
		} else {
			store_fd({ $name => \%{$name} }, $lfh) || die ("Couldn't save binary data to \"$in_dir/$name.bin\"!\n");
		}
		$lfh->close;
	}
}

# Dump memory from sar statistics to file for incremental use
sub dump_sar_binary
{
        my ($in_dir, $outfile) = @_;

	foreach my $name (@sar_to_be_stored) {
		my $lfh = new IO::File ">$in_dir/$name.bin";
		if (not defined $lfh) {
			die "FATAL: can't write to $in_dir/$name.bin, $!\n";
		}
		store_fd({ $name => \%{$name} }, $lfh) || die ("Couldn't save binary data to \"$in_dir/$name.bin\"!\n");
		$lfh->close;
	}
}

# Dump memory from system information to file for incremental use
sub dump_sys_binary
{
        my ($in_dir, $outfile) = @_;

	my $lfh = new IO::File ">$in_dir/$outfile";
	if (not defined $lfh) {
		die "FATAL: can't write to $in_dir/$outfile, $!\n";
	}
        store_fd({
		'sysinfo' => \%sysinfo,
        }, $lfh) || die ("Couldn't save binary data to «$in_dir/$outfile»!\n");
	$lfh->close;
}


# Load statistics from pg cache into memory
sub load_pg_binary
{
        my ($in_dir) = @_;

	foreach my $name (@pg_to_be_stored) {

		my $lfh = new IO::File "<$in_dir/$name.bin";
		if (not defined $lfh) {
			die "FATAL: can't write to $in_dir/$name.bin, $!\n";
		}
		my %stats = %{ fd_retrieve($lfh) };
		$lfh->close();

		# Setting global information
		if ($name eq 'global_infos') {

			my %_global_infos = %{$stats{global_infos}} ;
				foreach my $inf (keys %_global_infos) {
				if ($_global_infos{$inf} =~ /ARRAY/) {
					push(@{$inf}, @{$_global_infos{$inf}});
				} else {
					$global_infos{$inf} = $_global_infos{$inf};
				}
			}
			delete $stats{global_infos};

		} elsif (grep(/^$name$/, 'global_databases', 'global_tbspnames', )) {

			# Look for database and tablespace
			foreach my $d (@{$stats{$name}}) {
				push(@{$name}, $d) if (!grep(/^$d$/, @{$name}));
			}
			delete $stats{$name};

		} else {

			# Load other storages
			foreach my $m (keys %stats) {
				foreach my $t (keys %{$stats{$m}}) {
					if ($stats{$m}{$t} =~ /HASH/) {
						foreach my $d (keys %{$stats{$m}{$t}}) {
							if ($stats{$m}{$t}{$d} =~ /HASH/) {
								foreach my $k (keys %{$stats{$m}{$t}{$d}}) {
									${$m}{$t}{$d}{$k} = $stats{$m}{$t}{$d}{$k};
								}
							} elsif ($stats{$m}{$t}{$d} =~ /ARRAY/) {
								push(@{${$m}{$t}{$d}}, @{$stats{$m}{$t}{$d}});
							} else {
								${$m}{$t}{$d} = $stats{$m}{$t}{$d};
							}
						}
					} elsif ($stats{$m}{$t} =~ /ARRAY/) {
						push(@{${$m}{$t}}, @{$stats{$m}{$t}});
					} else {
						${$m}{$t} = $stats{$m}{$t};
					}
				}
			}
		}
	}
}

# Load statistics from sar cache into memory
sub load_sar_binary
{
        my ($in_dir) = @_;

	foreach my $name (@sar_to_be_stored) {

		my $lfh = new IO::File "<$in_dir/$name.bin";
		if (not defined $lfh) {
			die "FATAL: can't write to $in_dir/$name.bin, $!\n";
		}
		my %stats = %{ fd_retrieve($lfh) };
		$lfh->close();
		# Setting global information
		if ($name eq 'global_infos') {

			# Setting global information
			my %_global_infos = %{$stats{global_infos}} ;
			foreach my $inf (keys %_global_infos) {
				if ($_global_infos{$inf} =~ /ARRAY/) {
					push(@{$inf}, @{$_global_infos{$inf}});
				} else {
					$global_infos{$inf} = $_global_infos{$inf};
				}
			}
			delete $stats{global_infos};

		} else {

			# Load other sar storages
			foreach my $m (keys %stats) {
				foreach my $t (keys %{$stats{$m}}) {
					foreach my $d (keys %{$stats{$m}{$t}}) {
						if ($stats{$m}{$t}{$d} =~ /HASH/) {
							foreach my $k (keys %{$stats{$m}{$t}{$d}}) {
								${$m}{$t}{$d}{$k} = $stats{$m}{$t}{$d}{$k};
							}
						} else {
							${$m}{$t}{$d} = $stats{$m}{$t}{$d};
						}
					}
				}
			}
		}
	}
}

# Load statistics from sysinfo cache into memory
sub load_sys_binary
{
        my ($in_dir, $infile) = @_;

	my $lfh = new IO::File "<$in_dir/$infile";
	if (not defined $lfh) {
		die "FATAL: can't write to $in_dir/$infile, $!\n";
	}
	my %stats = %{ fd_retrieve($lfh) };
	$lfh->close();
	my %_sysinfo = %{$stats{sysinfo}};

	# Load other storages
	foreach my $s (keys %_sysinfo) {
		if ($_sysinfo{$s} =~ /HASH/) {
			foreach my $n (keys %{$_sysinfo{$s}}) {
				if ($_sysinfo{$s}{$n} =~ /HASH/) {
					foreach my $k (keys %{$_sysinfo{$s}{$n}}) {
						$sysinfo{$s}{$n}{$k} = $_sysinfo{$s}{$n}{$k};
					}
				} elsif ($_sysinfo{$s}{$n} =~ /ARRAY/) {
					foreach my $k (@{$_sysinfo{$s}{$n}}) {
						push(@{$sysinfo{$s}{$n}}, $k);
					}
				} else {
					$sysinfo{$s}{$n} = $_sysinfo{$s}{$n};
				}
			}
		} elsif ($_sysinfo{$s} =~ /ARRAY/) {
			foreach my $k (@{$_sysinfo{$s}}) {
				push(@{$sysinfo{$s}}, $k);
			}
		}
	}
}


sub empty_dataset
{
	my ($divid, $infos, $title) = @_;

	my $description = $infos->{description} || '';
	if ($title ne '') {
		$title = sprintf($infos->{title}, $title);
	} else {
		$title = $infos->{title};
	}

	my $str = qq{
<ul id="slides">
<li class="slide active-slide" id="$divid-slide">
      <div id="$divid"><br/><br/><br/><br/></div>
      <div class="row">
            <div class="col-md-12">
              <div class="panel panel-default">
              <div class="panel-heading">
              <h2>$title</h2>
		<p>$description</p>
              </div>
              <div class="panel-body">
		<div class="flotr-graph"><blockquote><b>NO DATASET</b></blockquote></div>
              </div>
              </div>
            </div><!--/span-->
      </div>
</li>
</ul>
};
	return $str;
}


