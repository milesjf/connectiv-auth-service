permit(
    principal,
    action == ExampleCo::Connectiv::Action::"access",
    resource
)
when {
    // `group` is required and must be "Admin"
    principal.group == "Admin"
    &&
    (
        // At least ONE of `dataProductAccess` or `department` must be present
        (principal has dataProductAccess && principal.dataProductAccess == "Owner")
        ||
        (principal has department && principal.department == "Leidos")
    )
};
