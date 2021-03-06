# coding=utf-8
"""Test functionality of the NCMCReporter."""
from protons import app
from protons.app import ncmcreporter as ncr
from simtk import unit, openmm as mm
from protons.app import GBAOABIntegrator, ForceFieldProtonDrive
from . import get_test_data
import uuid
import os
import pytest
from saltswap.wrappers import Salinator

travis = os.environ.get("TRAVIS", None)


@pytest.mark.skipif(travis == "true", reason="Travis segfaulting risk.")
class TestNCMCReporter(object):
    """Tests use cases for ConstantPHSimulation"""

    _default_platform = mm.Platform.getPlatformByName("Reference")

    def test_reports_no_perturbation(self):
        """Instantiate a ConstantPHSimulation at 300K/1 atm for a small peptide, don't save perturbation steps."""

        pdb = app.PDBxFile(
            get_test_data(
                "glu_ala_his-solvated-minimized-renamed.cif", "testsystems/tripeptides"
            )
        )
        forcefield = app.ForceField(
            "amber10-constph.xml", "ions_tip3p.xml", "tip3p.xml"
        )

        system = forcefield.createSystem(
            pdb.topology,
            nonbondedMethod=app.PME,
            nonbondedCutoff=1.0 * unit.nanometers,
            constraints=app.HBonds,
            rigidWater=True,
            ewaldErrorTolerance=0.0005,
        )

        temperature = 300 * unit.kelvin
        integrator = GBAOABIntegrator(
            temperature=temperature,
            collision_rate=1.0 / unit.picoseconds,
            timestep=2.0 * unit.femtoseconds,
            constraint_tolerance=1.0e-7,
            external_work=False,
        )
        ncmcintegrator = GBAOABIntegrator(
            temperature=temperature,
            collision_rate=1.0 / unit.picoseconds,
            timestep=2.0 * unit.femtoseconds,
            constraint_tolerance=1.0e-7,
            external_work=True,
        )

        compound_integrator = mm.CompoundIntegrator()
        compound_integrator.addIntegrator(integrator)
        compound_integrator.addIntegrator(ncmcintegrator)
        pressure = 1.0 * unit.atmosphere

        system.addForce(mm.MonteCarloBarostat(pressure, temperature))
        driver = ForceFieldProtonDrive(
            temperature,
            pdb.topology,
            system,
            forcefield,
            ["amber10-constph.xml"],
            pressure=pressure,
            perturbations_per_trial=3,
        )

        simulation = app.ConstantPHSimulation(
            pdb.topology,
            system,
            compound_integrator,
            driver,
            platform=self._default_platform,
        )
        simulation.context.setPositions(pdb.positions)
        simulation.context.setVelocitiesToTemperature(temperature)
        filename = uuid.uuid4().hex + ".nc"
        print("Temporary file: ", filename)
        newreporter = ncr.NCMCReporter(filename, 1)
        simulation.update_reporters.append(newreporter)

        # Regular MD step
        simulation.step(1)
        # Update the titration states using the uniform proposal
        simulation.update(4)
        # Basic checks for dimension
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["update"].size == 4
        ), "There should be 4 updates recorded."
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["residue"].size == 2
        ), "There should be 2 residues recorded."
        with pytest.raises(KeyError) as keyerror:
            newreporter.ncfile["Protons/NCMC"].dimensions["perturbation"]

        # Ensure clean exit
        newreporter.ncfile.sync()
        newreporter.ncfile.close()

    def test_reports_every_perturbation(self):
        """Instantiate a ConstantPHSimulation at 300K/1 atm for a small peptide, save every perturbation step."""

        pdb = app.PDBxFile(
            get_test_data(
                "glu_ala_his-solvated-minimized-renamed.cif", "testsystems/tripeptides"
            )
        )
        forcefield = app.ForceField(
            "amber10-constph.xml", "ions_tip3p.xml", "tip3p.xml"
        )

        system = forcefield.createSystem(
            pdb.topology,
            nonbondedMethod=app.PME,
            nonbondedCutoff=1.0 * unit.nanometers,
            constraints=app.HBonds,
            rigidWater=True,
            ewaldErrorTolerance=0.0005,
        )

        temperature = 300 * unit.kelvin
        integrator = GBAOABIntegrator(
            temperature=temperature,
            collision_rate=1.0 / unit.picoseconds,
            timestep=2.0 * unit.femtoseconds,
            constraint_tolerance=1.0e-7,
            external_work=False,
        )
        ncmcintegrator = GBAOABIntegrator(
            temperature=temperature,
            collision_rate=1.0 / unit.picoseconds,
            timestep=2.0 * unit.femtoseconds,
            constraint_tolerance=1.0e-7,
            external_work=True,
        )

        compound_integrator = mm.CompoundIntegrator()
        compound_integrator.addIntegrator(integrator)
        compound_integrator.addIntegrator(ncmcintegrator)
        pressure = 1.0 * unit.atmosphere

        system.addForce(mm.MonteCarloBarostat(pressure, temperature))
        driver = ForceFieldProtonDrive(
            temperature,
            pdb.topology,
            system,
            forcefield,
            ["amber10-constph.xml"],
            pressure=pressure,
            perturbations_per_trial=3,
        )

        simulation = app.ConstantPHSimulation(
            pdb.topology,
            system,
            compound_integrator,
            driver,
            platform=self._default_platform,
        )
        simulation.context.setPositions(pdb.positions)
        simulation.context.setVelocitiesToTemperature(temperature)
        filename = uuid.uuid4().hex + ".nc"
        print("Temporary file: ", filename)
        newreporter = ncr.NCMCReporter(filename, 1, cumulativeworkInterval=1)
        simulation.update_reporters.append(newreporter)

        # Regular MD step
        simulation.step(1)
        # Update the titration states using the uniform proposal
        simulation.update(4)
        # Basic checks for dimension
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["update"].size == 4
        ), "There should be 4 updates recorded."
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["residue"].size == 2
        ), "There should be 2 residues recorded."
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["perturbation"].size == 3
        ), "There should be max 3 perturbations recorded."

        # Ensure clean exit
        newreporter.ncfile.sync()
        newreporter.ncfile.close()

    def test_reports_every_perturbation_saltswap(self):
        """Instantiate a ConstantPHSimulation at 300K/1 atm for a small peptide, save every perturbation step, with saltswap."""

        pdb = app.PDBxFile(
            get_test_data(
                "glu_ala_his-solvated-minimized-renamed.cif", "testsystems/tripeptides"
            )
        )
        forcefield = app.ForceField(
            "amber10-constph.xml", "ions_tip3p.xml", "tip3p.xml"
        )

        system = forcefield.createSystem(
            pdb.topology,
            nonbondedMethod=app.PME,
            nonbondedCutoff=1.0 * unit.nanometers,
            constraints=app.HBonds,
            rigidWater=True,
            ewaldErrorTolerance=0.0005,
        )

        temperature = 300 * unit.kelvin
        integrator = GBAOABIntegrator(
            temperature=temperature,
            collision_rate=1.0 / unit.picoseconds,
            timestep=2.0 * unit.femtoseconds,
            constraint_tolerance=1.0e-7,
            external_work=False,
        )
        ncmcintegrator = GBAOABIntegrator(
            temperature=temperature,
            collision_rate=1.0 / unit.picoseconds,
            timestep=2.0 * unit.femtoseconds,
            constraint_tolerance=1.0e-7,
            external_work=True,
        )

        compound_integrator = mm.CompoundIntegrator()
        compound_integrator.addIntegrator(integrator)
        compound_integrator.addIntegrator(ncmcintegrator)
        pressure = 1.0 * unit.atmosphere

        system.addForce(mm.MonteCarloBarostat(pressure, temperature))
        driver = ForceFieldProtonDrive(
            temperature,
            pdb.topology,
            system,
            forcefield,
            ["amber10-constph.xml"],
            pressure=pressure,
            perturbations_per_trial=3,
        )

        simulation = app.ConstantPHSimulation(
            pdb.topology,
            system,
            compound_integrator,
            driver,
            platform=self._default_platform,
        )
        simulation.context.setPositions(pdb.positions)
        simulation.context.setVelocitiesToTemperature(temperature)
        filename = uuid.uuid4().hex + ".nc"
        print("Temporary file: ", filename)
        # The salinator initializes the system salts
        salinator = Salinator(
            context=simulation.context,
            system=simulation.system,
            topology=simulation.topology,
            ncmc_integrator=simulation.integrator.getIntegrator(1),
            salt_concentration=0.2 * unit.molar,
            pressure=pressure,
            temperature=temperature,
        )
        salinator.neutralize()
        salinator.initialize_concentration()
        swapper = salinator.swapper
        driver.enable_neutralizing_ions(swapper)

        newreporter = ncr.NCMCReporter(filename, 1, cumulativeworkInterval=1)
        simulation.update_reporters.append(newreporter)

        # Regular MD step
        simulation.step(1)
        # Update the titration states using the uniform proposal
        simulation.update(4)
        # Basic checks for dimension
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["update"].size == 4
        ), "There should be 4 updates recorded."
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["residue"].size == 2
        ), "There should be 2 residues recorded."
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["perturbation"].size == 3
        ), "There should be max 3 perturbations recorded."
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["ion_site"].size == 1269
        ), "The system should have 1269 potential ion sites."

        # Ensure clean exit
        newreporter.ncfile.sync()
        newreporter.ncfile.close()

    def test_reports_every_2nd_perturbation(self):
        """Instantiate a ConstantPHSimulation at 300K/1 atm for a small peptide, save every 2nd perturbation step."""

        pdb = app.PDBxFile(
            get_test_data(
                "glu_ala_his-solvated-minimized-renamed.cif", "testsystems/tripeptides"
            )
        )
        forcefield = app.ForceField(
            "amber10-constph.xml", "ions_tip3p.xml", "tip3p.xml"
        )

        system = forcefield.createSystem(
            pdb.topology,
            nonbondedMethod=app.PME,
            nonbondedCutoff=1.0 * unit.nanometers,
            constraints=app.HBonds,
            rigidWater=True,
            ewaldErrorTolerance=0.0005,
        )

        temperature = 300 * unit.kelvin
        integrator = GBAOABIntegrator(
            temperature=temperature,
            collision_rate=1.0 / unit.picoseconds,
            timestep=2.0 * unit.femtoseconds,
            constraint_tolerance=1.0e-7,
            external_work=False,
        )
        ncmcintegrator = GBAOABIntegrator(
            temperature=temperature,
            collision_rate=1.0 / unit.picoseconds,
            timestep=2.0 * unit.femtoseconds,
            constraint_tolerance=1.0e-7,
            external_work=True,
        )

        compound_integrator = mm.CompoundIntegrator()
        compound_integrator.addIntegrator(integrator)
        compound_integrator.addIntegrator(ncmcintegrator)
        pressure = 1.0 * unit.atmosphere

        system.addForce(mm.MonteCarloBarostat(pressure, temperature))
        driver = ForceFieldProtonDrive(
            temperature,
            pdb.topology,
            system,
            forcefield,
            ["amber10-constph.xml"],
            pressure=pressure,
            perturbations_per_trial=3,
        )

        simulation = app.ConstantPHSimulation(
            pdb.topology,
            system,
            compound_integrator,
            driver,
            platform=self._default_platform,
        )
        simulation.context.setPositions(pdb.positions)
        simulation.context.setVelocitiesToTemperature(temperature)
        filename = uuid.uuid4().hex + ".nc"
        print("Temporary file: ", filename)
        newreporter = ncr.NCMCReporter(filename, 1, cumulativeworkInterval=2)
        simulation.update_reporters.append(newreporter)

        # Regular MD step
        simulation.step(1)
        # Update the titration states using the uniform proposal
        simulation.update(4)
        # Basic checks for dimension
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["update"].size == 4
        ), "There should be 4 updates recorded."
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["residue"].size == 2
        ), "There should be 2 residues recorded."
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["perturbation"].size == 2
        ), "There should be max 2 perturbations recorded."

        # Ensure clean exit
        newreporter.ncfile.sync()
        newreporter.ncfile.close()

    def test_reports_with_coords(self):
        """Instantiate a ConstantPHSimulation at 300K/1 atm for a small peptide, store_coordinates."""

        pdb = app.PDBxFile(
            get_test_data(
                "glu_ala_his-solvated-minimized-renamed.cif", "testsystems/tripeptides"
            )
        )
        forcefield = app.ForceField(
            "amber10-constph.xml", "ions_tip3p.xml", "tip3p.xml"
        )

        system = forcefield.createSystem(
            pdb.topology,
            nonbondedMethod=app.PME,
            nonbondedCutoff=1.0 * unit.nanometers,
            constraints=app.HBonds,
            rigidWater=True,
            ewaldErrorTolerance=0.0005,
        )

        temperature = 300 * unit.kelvin
        integrator = GBAOABIntegrator(
            temperature=temperature,
            collision_rate=1.0 / unit.picoseconds,
            timestep=2.0 * unit.femtoseconds,
            constraint_tolerance=1.0e-7,
            external_work=False,
        )
        ncmcintegrator = GBAOABIntegrator(
            temperature=temperature,
            collision_rate=1.0 / unit.picoseconds,
            timestep=2.0 * unit.femtoseconds,
            constraint_tolerance=1.0e-7,
            external_work=True,
        )

        compound_integrator = mm.CompoundIntegrator()
        compound_integrator.addIntegrator(integrator)
        compound_integrator.addIntegrator(ncmcintegrator)
        pressure = 1.0 * unit.atmosphere

        system.addForce(mm.MonteCarloBarostat(pressure, temperature))
        driver = ForceFieldProtonDrive(
            temperature,
            pdb.topology,
            system,
            forcefield,
            ["amber10-constph.xml"],
            pressure=pressure,
            perturbations_per_trial=3,
        )

        simulation = app.ConstantPHSimulation(
            pdb.topology,
            system,
            compound_integrator,
            driver,
            platform=self._default_platform,
        )
        simulation.context.setPositions(pdb.positions)
        simulation.context.setVelocitiesToTemperature(temperature)
        filename = uuid.uuid4().hex + ".nc"
        print("Temporary file: ", filename)
        newreporter = ncr.NCMCReporter(filename, 1, store_coords=True)
        simulation.update_reporters.append(newreporter)

        # Regular MD step
        simulation.step(1)
        # Update the titration states using the uniform proposal
        simulation.update(4)
        # Basic checks for dimension
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["update"].size == 4
        ), "There should be 4 updates recorded."
        assert (
            newreporter.ncfile["Protons/NCMC"].dimensions["residue"].size == 2
        ), "There should be 2 residues recorded."
        with pytest.raises(KeyError) as keyerror:
            newreporter.ncfile["Protons/NCMC"].dimensions["perturbation"]

        # Ensure clean exit
        newreporter.ncfile.sync()
        newreporter.ncfile.close()
