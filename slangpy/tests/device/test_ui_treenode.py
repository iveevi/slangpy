# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

import slangpy as spy


def test_treenode_defaults() -> None:
    node = spy.ui.TreeNode(None)
    assert node.label == ""
    assert node.open is False
    assert isinstance(node, spy.ui.Widget)


def test_treenode_construct_with_args() -> None:
    node = spy.ui.TreeNode(None, "root", open=True)
    assert node.label == "root"
    assert node.open is True


def test_treenode_properties_round_trip() -> None:
    node = spy.ui.TreeNode(None, "a")
    node.label = "renamed"
    node.open = True
    assert node.label == "renamed"
    assert node.open is True
    node.open = False
    assert node.open is False


def test_treenode_parents_children() -> None:
    node = spy.ui.TreeNode(None, "root")
    child = spy.ui.Text(node, "child")
    assert len(node) == 1
    assert node[0] is child
    assert child.parent is node


def test_treenode_nested() -> None:
    root = spy.ui.TreeNode(None, "scene", open=True)
    geometry = spy.ui.TreeNode(root, "geometry", open=True)
    spheres = spy.ui.TreeNode(geometry, "spheres")
    leaf = spy.ui.Text(spheres, "sphere 0")

    assert root[0] is geometry
    assert geometry[0] is spheres
    assert spheres[0] is leaf
    assert leaf.parent.parent.parent is root
    assert isinstance(geometry, spy.ui.TreeNode)
