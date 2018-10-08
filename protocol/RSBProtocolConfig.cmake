get_filename_component(CONFIG_DIR "${CMAKE_CURRENT_LIST_FILE}" PATH)

if(EXISTS "${CONFIG_DIR}/CMakeCache.txt")

    include("${CONFIG_DIR}/RSBProtocolBuildTreeSettings.cmake")

else()

    foreach(F rsb/protocol/Notification.proto;rsb/protocol/EventId.proto;rsb/protocol/EventMetaData.proto;rsb/protocol/FragmentedNotification.proto;rsb/protocol/collections/EventsByScopeMap.proto;rsb/protocol/operatingsystem/__package.proto;rsb/protocol/operatingsystem/Process.proto;rsb/protocol/operatingsystem/Host.proto;rsb/protocol/introspection/__package.proto;rsb/protocol/introspection/Hello.proto;rsb/protocol/introspection/Bye.proto)
        set(PROTOFILES_WITH_ROOT ${PROTOFILES_WITH_ROOT} "${CONFIG_DIR}/${F}")
    endforeach()

    set(RSBPROTO_ROOT "${CONFIG_DIR}")
    set(RSBPROTO_FILES "${PROTOFILES_WITH_ROOT}")

endif()
