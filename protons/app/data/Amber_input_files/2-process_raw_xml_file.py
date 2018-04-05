# coding=utf-8
"""
This script parses the raw parmed output, and adds protons blocks for all the residues
in parmed.amber.titratable residues

"""
from lxml import etree
from parmed.amber import titratable_residues
from copy import deepcopy
import os
# Extract the Titratable residue objects from parmed and store them in a dictionary for easy access
residue_objects = dict()
for key in titratable_residues.titratable_residues:
    residue_objects[key] = getattr(titratable_residues, key)

from simtk.openmm import app, openmm

# Validate that the initial file can be parsed by openmm
x = app.ForceField('Amber_input_files/raw-amber10-constph-tmp.xml')

xml_parser = etree.XMLParser(remove_blank_text=True, remove_comments=True)
xmltree = etree.parse("Amber_input_files/raw-amber10-constph-tmp.xml", xml_parser)

pdbnames = etree.parse(os.path.join(os.path.dirname(app.__file__), 'data', 'pdbNames.xml'), xml_parser)


for residue in xmltree.xpath('/ForceField/Residues/Residue'):
    residue_name = residue.get('name')

    # Look up the canonical residue name used by OpenMM (based on pdbNames.xml)
    # Checks if any attribute of the residue (alt names) is the residue name
    # If none are found, no renaming takes place
    residue_pdbname = pdbnames.xpath('//Residue[@*="{0}"]'.format(residue_name))

    # If there is one, check for atom names
    if len(residue_pdbname) == 1:

        # Look up the canonical atom names used by OpenMM (based on pdbNames.xml)
        for atom in residue.xpath('Atom'):
            aname = atom.get('name')
            # Look for altnames that match the current atom
            # if any attribute of the atom is the current atom name
            pdbatomname = residue_pdbname[0].xpath('Atom[@*="{}"]'.format(aname))
            # There is one atom (wouldn't expect duplicates)
            if len(pdbatomname) == 1:
                preferred_name = pdbatomname[0].get('name')
                atom.set('name', preferred_name)
                # Adjust bonds accordingly
                for bond in residue.xpath('Bond[@atomName1="{0}" or @atomName2="{0}"]'.format(aname)):
                    if bond.get("atomName1") == aname:
                        bond.set("atomName1", preferred_name)
                    elif bond.get("atomName2") == aname:
                        bond.set("atomName2", preferred_name)
            # In case we have duplicate atom names
            if len(pdbatomname) > 1:
                print("Ambiguous atomname, not renaming {}".format(aname))

    # There typically shouldn't be more than 1 alternative residue name, but this is to make sure the user is made aware
    elif len(residue_pdbname) > 1:
        print("Ambiguous residue {}. Not renaming".format(residue_name))

    # CYX residues have an external bond from SG that needs explicit adding
    if residue_name.endswith("CYX"):
        residue.append(etree.fromstring('<ExternalBond atomName="SG"/>'))

    if residue_name in residue_objects:

        residue_state_parameters = residue_objects[residue_name]
        # Get the atom block
        atoms = [atom for atom in residue.xpath('Atom')]

        # Delete the old block. Will put back later with the charges of state 0
        for atom in residue.xpath('Atom'):
            atom.getparent().remove(atom)

        # Create a protons block
        num_states = len(residue_state_parameters.states)
        protons_str = '<Protons number_of_states="{}"/>'.format(num_states)
        protons_block = etree.fromstring(protons_str)

        # Note that there is no log_probability specified for these, because based on the pH and hardcoded pKa
        # the calibration utility takes care of this.
        template = '<State index="{}" g_k="0.0" proton_count="{}"/>'
        # Loop through all states and add them to the protons block
        for index,state in enumerate(residue_state_parameters.states):
            state_block = etree.fromstring(template.format(index, state.protcnt))
            # loop through all atoms and fill in the charges
            charges = dict(zip(residue_state_parameters.atom_list, state.charges))
            for atom_index,atom in enumerate(atoms):
                protons_atom = deepcopy(atom)
                parmed_atomname = atom.get("name")

                # compatibility fix since this is encoded differently in parmed titratable residues
                if parmed_atomname == "OP1":
                    parmed_atomname = "O1P"
                elif parmed_atomname == "OP2":
                    parmed_atomname = "O2P"
                elif parmed_atomname == "H5'":
                    parmed_atomname = "H5'1"
                elif parmed_atomname == "H5''":
                    parmed_atomname = "H5'2"
                elif parmed_atomname == "H2'":
                    parmed_atomname = "H2'1"
                elif parmed_atomname == "H2''":
                    parmed_atomname = "H2'2"
                elif parmed_atomname == "HO2'":
                    parmed_atomname = "HO'2"
                try:
                    protons_atom.set("charge", str(charges[parmed_atomname]))
                except:
                    raise Exception(residue_name)
                # Keep the charges of the initial state as the reference state
                if index == 0:
                    atoms[atom_index] = deepcopy(protons_atom)
                state_block.append(protons_atom)

            protons_block.append(state_block)
        residue.append(protons_block)

        # Add the atoms back to the residue list in the original order.
        for atom in reversed(atoms):
            residue.insert(0, atom)

# Write out to file
xmlstring = etree.tostring(xmltree,encoding="utf-8", pretty_print=True, xml_declaration=False)
xmlstring = xmlstring.decode("utf-8")

with open('amber10-constph-tmp.xml', 'w') as fstream:
    fstream.write(xmlstring)

# Validate that the resulting file can be read by openmm
y = app.ForceField('amber10-constph-tmp.xml')
