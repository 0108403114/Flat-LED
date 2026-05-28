idf_component_register(SRCS "app_main.c"
                    INCLUDE_DIRS "." "../../../shared/include"
                    REQUIRES led_strip driver esp_system)
