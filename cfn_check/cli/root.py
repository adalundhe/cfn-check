import asyncio
import sys

from cocoa.cli import CLI, CLIStyle
from cocoa.ui.config.mode import TerminalMode
from cocoa.ui.components.terminal import Section, SectionConfig
from cocoa.ui.components.header import Header, HeaderConfig
from cocoa.ui.components.terminal import Terminal, EngineConfig

from .render import render
from .validate import validate

async def create_header(
    terminal_mode: TerminalMode = "full", 
):
    
    cfn_check_terminal_mode = "extended"
    if terminal_mode == "ci":
        cfn_check_terminal_mode = "compatability"

    header = Section(
        SectionConfig(height="xx-small", width="large"),
        components=[
            Header(
                "header",
                HeaderConfig(
                    header_text="cfn-check",
                    color="indian_red_3",
                    attributes=["bold"],
                    terminal_mode=cfn_check_terminal_mode,
                    font='cyberpunk'
                ),
            ),
        ],
    )

    terminal = Terminal(
        [
            header,
        ],
        config=EngineConfig(
            max_height=40,
            max_width=120
        )
    )

    return await terminal.render_once()



@CLI.root( 
    render, 
    validate,
    global_styles=CLIStyle(
        header=create_header,
        flag_description_color="white",
        error_color="indian_red_3",
        error_attributes=["italic"],
        flag_color="indian_red_3",
        text_color="slate_blue_2",
        subcommand_color="slate_blue_2",
        indentation=5,
        terminal_mode="extended",
    ),
)
async def cfn_check():
    '''
    Check and test CloudFormation
    '''



def run():
    asyncio.run(CLI.run(sys.argv[1:]))