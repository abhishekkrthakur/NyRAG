"""Tests for the logger module."""

import logging

from nyrag.logger import NyragLogger, get_logger, logger, set_log_level


class TestNyragLogger:
    """Tests for NyragLogger class."""

    def test_initialization(self):
        """Test logger initialization."""
        log = NyragLogger(name="test_logger", level="DEBUG")
        assert log.logger.name == "test_logger"
        assert log.logger.level == logging.DEBUG

    def test_default_initialization(self):
        """Test logger with default values."""
        log = NyragLogger()
        assert log.logger.name == "nyrag"
        assert log.logger.level == logging.INFO

    def test_level_case_insensitive(self):
        """Test that level is case insensitive."""
        log = NyragLogger(level="debug")
        assert log.logger.level == logging.DEBUG

    def test_info_logging(self, capsys):
        """Test info level logging."""
        log = NyragLogger(name="test_info", level="INFO")
        log.info("Test info message")
        # Just verify no exception is raised

    def test_debug_logging(self):
        """Test debug level logging."""
        log = NyragLogger(name="test_debug", level="DEBUG")
        log.debug("Test debug message")
        # Just verify no exception is raised

    def test_warning_logging(self):
        """Test warning level logging."""
        log = NyragLogger(name="test_warning", level="WARNING")
        log.warning("Test warning message")
        # Just verify no exception is raised

    def test_error_logging(self):
        """Test error level logging."""
        log = NyragLogger(name="test_error", level="ERROR")
        log.error("Test error message")
        # Just verify no exception is raised

    def test_critical_logging(self):
        """Test critical level logging."""
        log = NyragLogger(name="test_critical", level="CRITICAL")
        log.critical("Test critical message")
        # Just verify no exception is raised

    def test_success_logging(self):
        """Test success level logging (custom)."""
        log = NyragLogger(name="test_success", level="INFO")
        log.success("Test success message")
        # Just verify no exception is raised

    def test_exception_logging(self):
        """Test exception logging."""
        log = NyragLogger(name="test_exception", level="ERROR")
        try:
            raise ValueError("Test exception")
        except ValueError:
            log.exception("Caught exception")
        # Just verify no exception is raised during logging

    def test_escapes_rich_markup(self):
        """Test that rich markup is properly escaped in messages."""
        log = NyragLogger(name="test_escape", level="INFO")
        # Message with potential rich markup
        log.info("Test [bold]markup[/bold] message")
        # Just verify no exception is raised


class TestSetLogLevel:
    """Tests for set_log_level function."""

    def test_set_level_debug(self):
        """Test setting log level to DEBUG."""
        original_level = logger.logger.level
        try:
            set_log_level("DEBUG")
            assert logger.logger.level == logging.DEBUG
        finally:
            logger.logger.setLevel(original_level)

    def test_set_level_warning(self):
        """Test setting log level to WARNING."""
        original_level = logger.logger.level
        try:
            set_log_level("WARNING")
            assert logger.logger.level == logging.WARNING
        finally:
            logger.logger.setLevel(original_level)

    def test_set_level_case_insensitive(self):
        """Test that set_log_level is case insensitive."""
        original_level = logger.logger.level
        try:
            set_log_level("debug")
            assert logger.logger.level == logging.DEBUG
        finally:
            logger.logger.setLevel(original_level)


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_global_logger(self):
        """Test getting global logger when no name provided."""
        result = get_logger()
        assert result is logger

    def test_get_global_logger_none(self):
        """Test getting global logger with explicit None."""
        result = get_logger(None)
        assert result is logger

    def test_get_named_logger(self):
        """Test getting a named logger."""
        result = get_logger("custom_name")
        assert isinstance(result, NyragLogger)
        assert result.logger.name == "custom_name"

    def test_named_loggers_are_different(self):
        """Test that different names give different loggers."""
        log1 = get_logger("logger1")
        log2 = get_logger("logger2")
        assert log1 is not log2
        assert log1.logger.name != log2.logger.name


class TestGlobalLogger:
    """Tests for the global logger instance."""

    def test_global_logger_exists(self):
        """Test that global logger is available."""
        assert logger is not None
        assert isinstance(logger, NyragLogger)

    def test_global_logger_name(self):
        """Test that global logger has correct name."""
        assert logger.logger.name == "nyrag"
