from discord import ChannelType, CategoryChannel, TextChannel, VoiceChannel, Role

from helpers import format_channel
from models import ChannelDescription, RoleDescription


def check_channel_type(channel_description: ChannelDescription, errors):
    if ((channel_description.channel_type is ChannelType.category
         and not isinstance(channel_description.object_reference, CategoryChannel))
            or (channel_description.channel_type is ChannelType.text
                and not isinstance(channel_description.object_reference, TextChannel))
            or (channel_description.channel_type is ChannelType.voice
                and not isinstance(channel_description.object_reference, VoiceChannel))):
        errors.append(f"`{channel_description}`: reference has not the correct type")
        return True
    return False


def check_channel_description(channel_description: ChannelDescription, guild, guild_channels, errors,
                              allowed_role_descriptions=None):
    allowed_role_descriptions = allowed_role_descriptions or []
    has_errors = False
    if channel_description.object_reference is None:
        has_errors = True
        errors.append(f"`{channel_description}`: no corresponding channel / reference has not been set to description")
    elif channel_description.object_reference not in guild_channels:
        has_errors = True
        errors.append(f"`{channel_description}`: channel referenced is not in guild")
    elif check_channel_type(channel_description, errors):
        has_errors = True
    elif channel_description.category:
        if channel_description.object_reference.category != channel_description.category:
            has_errors = True
            errors.append(f"Category {format_channel(channel_description.category, pretty=True)} "
                          f"defined for channel `{channel_description}` is not the one found: "
                          f"{format_channel(channel_description.object_reference.category, pretty=True)}")
        # _check_channel_description(ChannelDescription.from_channel(channel_description.category), guild_channels,
        #                            errors)
    if has_errors or len(errors) > 10:  # enough errors!
        return
    field_errors = channel_description.compare_to_object_reference(allowed_role_descriptions)
    if not field_errors:
        field_errors = channel_description.compare_object_and_real_references(guild=guild)
    errors.extend(field_errors)


def check_role_description(role_description: RoleDescription, guild, errors):
    guild_roles = guild.roles
    if role_description.object_reference is None:
        errors.append(f"`{role_description}`: no corresponding role in guild")
    elif role_description.object_reference not in guild_roles:
        errors.append(f"`{role_description}`: role referenced is not in guild")
    elif not isinstance(role_description.object_reference, Role):
        errors.append(f"`{role_description}`: reference is not a Role")
    if errors:  # enough errors!
        return
    field_errors = role_description.compare_to_object_reference()
    if not field_errors:
        field_errors = role_description.compare_object_and_real_references(guild=guild)
    errors.extend(field_errors)
