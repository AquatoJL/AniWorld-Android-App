import os
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom

class cXmlHandler:
    @staticmethod
    def read_xml(xml_path):
        """
        Reads and parses the XML file, returning the tree and root.
        :param xml_path: Path to the XML file.
        :return: (tree, root)
        """
        tree = ET.parse(xml_path)
        root = tree.getroot()
        return tree, root

    @staticmethod
    def write_xml(tree, xml_path):
        """
        Writes the XML tree to the file, pretty-printed.
        :param tree: ElementTree object.
        :param xml_path: Path to the XML file.
        """
        xml_str = ET.tostring(tree.getroot(), encoding='utf-8')
        pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="\t", encoding='utf-8')
        # Remove empty lines
        pretty_xml_clean = '\n'.join([line for line in pretty_xml.decode('utf-8').splitlines() if line.strip()])
        # Fix mistakes (can be removed later)
        # not needed currently because they will be replaced by the scraper settings
        #pretty_xml_clean = re.sub(r'</dependencies>\s*&gt;', '</dependencies>', pretty_xml_clean)
        #pretty_xml_clean = re.sub(r'</default>\s*<default/>', '</default>', pretty_xml_clean)
        tmp_path = xml_path + ".tmp"
        with open(tmp_path, 'wb') as f:
            f.write(pretty_xml_clean.encode('utf-8'))
        os.replace(tmp_path, xml_path)  # Atomic replace

    @staticmethod
    def get_group_ids_from_categories(root, category_ids=None):
        """
        Returns a list of all group ids from the specified categories in the XML root.
        :param root: XML root element.
        :param category_ids: List of category id strings to filter by, or None for all.
        :return: List of group ids.
        """
        group_ids = []
        for category in root.findall('.//category'):
            cat_id = category.get('id')
            if category_ids is None or (cat_id and cat_id in category_ids):
                for group in category.findall('group'):
                    group_id = group.get('id')
                    if group_id:
                        group_ids.append(group_id)
        return group_ids

    @staticmethod
    def delete_groups_from_categories(root, category_ids, group_ids):
        """
        Deletes all groups from categories with given category_ids in the XML root,
        except those whose group id ends with any of the strings in group_ids.
        :param root: XML root element.
        :param category_ids: List of category id strings to filter by, or None for all.
        :param group_ids: List of group id suffixes to keep.
        :return: True if any group was deleted, False otherwise.
        """
        deleted = False
        for category in root.findall('.//category'):
            cat_id = category.get('id')
            if category_ids is None or (cat_id and cat_id in category_ids):
                groups_to_remove = []
                for group in category.findall('group'):
                    gid = group.get('id')
                    # Only keep groups whose id ends with one of the group_ids
                    if not gid or not any(gid.endswith(group_id) for group_id in group_ids):
                        groups_to_remove.append(group)
                for group in groups_to_remove:
                    category.remove(group)
                    deleted = True
        return deleted

    @staticmethod
    def _normalize_xml(xml_str):
        """
        Parse XML string and return a normalized string with no whitespace between tags.
        """
        def strip_whitespace(elem):
            # Remove leading/trailing whitespace from text and tail
            if elem.text:
                elem.text = elem.text.strip()
            if elem.tail:
                elem.tail = elem.tail.strip()
            for child in elem:
                strip_whitespace(child)
        elem = ET.fromstring(xml_str)
        strip_whitespace(elem)
        return ET.tostring(elem, encoding='utf-8').decode('utf-8')

    @staticmethod
    def sync_group_from_scraper_settings(root, settings_dict, category_ids=None):
        """
        Syncs <group> elements from a dictionary into the settings.xml tree.
        If a group with the same id exists and is identical (ignoring whitespace), do nothing.
        If a group with the same id exists but differs, replace it.
        If not found, add the group in sorted order by group id within the specified categories.
        Only the affected category will be changed.
        :param root: XML root element (settings.xml).
        :param settings_dict: Dictionary where key is group id and value is the group XML string.
        :param category_ids: List of category id strings to filter by, or None for all.
        :return: True if changes were made, False otherwise.
        """
        changed = False
        for group_id, scraper_settings_xml in settings_dict.items():
            # Parse the incoming group XML
            try:
                group_elem = ET.fromstring(scraper_settings_xml.strip())
            except ET.ParseError:
                wrapped = f"<root>{scraper_settings_xml.strip()}</root>"
                group_elem = ET.fromstring(wrapped)[0]

            # Find categories to search/add in
            categories = []
            for category in root.findall('.//category'):
                cat_id = category.get('id')
                if category_ids is None or (cat_id and cat_id in category_ids):
                    categories.append(category)
            if not categories:
                raise ValueError("No matching <category> found in settings.xml to add the group.")

            # Search for existing group in the filtered categories
            parent_category = None
            existing_group = None
            for category in categories:
                for group in category.findall('group'):
                    gid = group.get('id')
                    # Match group if its id ends with the new group_id (allow prefix)
                    if gid and gid.endswith(group_id):
                        parent_category = category
                        existing_group = group
                        break
                if parent_category:
                    break

            # Normalize both XMLs for comparison
            new_group_norm = cXmlHandler._normalize_xml(ET.tostring(group_elem, encoding='utf-8').decode('utf-8'))
            if existing_group:
                existing_group_norm = cXmlHandler._normalize_xml(ET.tostring(existing_group, encoding='utf-8').decode('utf-8'))
                if new_group_norm == existing_group_norm:
                    continue  # No change needed
                # Replace the group in the affected category, preserving order
                groups = list(parent_category.findall('group'))
                idx = groups.index(existing_group)
                parent_category.remove(existing_group)
                parent_category.insert(idx, group_elem)
                changed = True
            else:
                # Add the group in sorted order by group id in the first matching category only
                target_category = categories[0]
                groups = list(target_category.findall('group')) + [group_elem]
                groups.sort(key=lambda g: g.get('id') or "")
                # Remove all and re-add sorted
                for g in target_category.findall('group'):
                    target_category.remove(g)
                for g in groups:
                    target_category.append(g)
                changed = True
        return changed
